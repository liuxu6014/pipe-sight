"""科技情报数据处理服务。"""

from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

DEFAULT_HTTP_PORT = 80
DEFAULT_HTTPS_PORT = 443


class PipelineDataProcessingService:
    """科技情报数据规范化、质量评估、分类和过滤契约。

    采集链路先用固定规则完成低成本预过滤，并把发布中的 Prompt 快照写入
    ``processing.filter``。InsightHub Worker 对预过滤通过的记录继续执行这份
    快照对应的模型过滤；因此管理端配置既有可审计快照，也真正参与最终判定。
    """

    VERSION = 'pipesight-data-v1'
    SIMHASH_DISTANCE_THRESHOLD = 12
    MIN_TITLE_LENGTH = 5
    MIN_CONTENT_LENGTH = 40
    MIN_RELEVANCE_SCORE = 70
    LONG_CONTENT_LENGTH = 500
    _tracking_params = frozenset(
        {
            'fbclid',
            'from',
            'isappinstalled',
            'ref',
            'scene',
            'spm',
            'utm_campaign',
            'utm_content',
            'utm_medium',
            'utm_source',
            'utm_term',
            'wxfrom',
        }
    )
    _tag_rules = (
        ('管道完整性', ('管道', 'pipeline', '完整性', 'integrity')),
        ('腐蚀防护', ('腐蚀', '阴极保护', '防腐', 'corrosion')),
        ('监测预警', ('监测', '检测', '预警', '泄漏', '应力', 'monitor', 'leak')),
        ('数字化智能化', ('数字化', '智能化', '数字孪生', '人工智能', 'digital', 'smart')),
        ('工程建设', ('工程', '建设', '施工', '项目', 'construction')),
        ('安全环保', ('安全', '风险', '环保', '应急', 'safety', 'risk')),
    )

    @classmethod
    def normalize_text(cls, value: Any) -> str:
        text = '' if value is None else str(value)
        text = re.sub(r'<(script|style)\b[^>]*>.*?</\1>', ' ', text, flags=re.I | re.S)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html.unescape(text)
        text = unicodedata.normalize('NFKC', text)
        text = text.replace('\u200b', '').replace('\ufeff', '').replace('\xa0', ' ')
        return re.sub(r'\s+', ' ', text).strip()

    @classmethod
    def canonicalize_url(cls, value: Any) -> str:
        raw = cls.normalize_text(value)
        if not raw:
            return ''
        try:
            parsed = urlsplit(raw)
        except ValueError:
            return ''
        if parsed.scheme.lower() not in {'http', 'https'} or not parsed.netloc:
            return ''
        hostname = (parsed.hostname or '').lower().rstrip('.')
        if not hostname:
            return ''
        try:
            port = parsed.port
        except ValueError:
            return ''
        netloc = hostname
        if ':' in hostname and not hostname.startswith('['):
            netloc = f'[{hostname}]'
        default_port = (parsed.scheme.lower() == 'http' and port == DEFAULT_HTTP_PORT) or (
            parsed.scheme.lower() == 'https' and port == DEFAULT_HTTPS_PORT
        )
        if port and not default_port:
            netloc = f'{netloc}:{port}'
        query = [
            (key, item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() not in cls._tracking_params and not key.lower().startswith('utm_')
        ]
        path = parsed.path or '/'
        if path != '/':
            path = path.rstrip('/')
        return urlunsplit((parsed.scheme.lower(), netloc, path, urlencode(sorted(query)), ''))

    @classmethod
    def normalize_doi(cls, value: Any) -> str:
        doi = cls.normalize_text(value).lower()
        doi = re.sub(r'^https?://(dx\.)?doi\.org/', '', doi)
        return doi.removeprefix('doi:').strip().rstrip('.,;')

    @classmethod
    def content_hash(cls, title: Any, body: Any, summary: Any = '') -> str:
        normalized = '\n'.join(
            [cls.normalize_text(title).casefold(), cls.normalize_text(body or summary).casefold()]
        )
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

    @classmethod
    def simhash(cls, value: Any) -> str:
        text = cls.normalize_text(value).casefold()
        tokens: list[str] = []
        for chunk in re.findall(r'[\u4e00-\u9fff]+|[a-z0-9]+', text):
            if re.fullmatch(r'[\u4e00-\u9fff]+', chunk):
                tokens.extend(chunk[index:index + 2] for index in range(max(0, len(chunk) - 1)))
                tokens.extend(chunk[index:index + 3] for index in range(max(0, len(chunk) - 2)))
            else:
                tokens.append(chunk)
        if not tokens:
            return '0000000000000000'
        vector = [0] * 64
        for token in tokens:
            digest = hashlib.sha256(token.encode('utf-8')).digest()
            value_hash = int.from_bytes(digest[:8], 'big')
            for bit in range(64):
                vector[bit] += 1 if value_hash & (1 << bit) else -1
        fingerprint = sum(1 << bit for bit, weight in enumerate(vector) if weight >= 0)
        return f'{fingerprint:016x}'

    @classmethod
    def simhash_distance(cls, left: str, right: str) -> int:
        return (int(left, 16) ^ int(right, 16)).bit_count()

    @classmethod
    def _classification(cls, title: str, content: str, source_type: str) -> tuple[int, list[str], str]:
        title_lower = title.casefold()
        content_lower = content.casefold()
        tags: list[str] = []
        title_hits = 0
        for tag, keywords in cls._tag_rules:
            if any(keyword.casefold() in content_lower for keyword in keywords):
                tags.append(tag)
            if any(keyword.casefold() in title_lower for keyword in keywords):
                title_hits += 1
        score = 25 + min(35, len(tags) * 10) + min(20, title_hits * 10)
        if len(content) >= cls.LONG_CONTENT_LENGTH:
            score += 10
        if source_type == 'paper':
            score += 5
        score = min(100, score)
        if not tags:
            tags = ['待人工确认']
        category = '科技论文' if source_type == 'paper' else '管网科技'
        return score, tags, category

    @classmethod
    def _render_prompt(cls, template: Any, values: dict[str, str]) -> str:
        """Render supported Prompt variables for an auditable execution trace."""
        text = '' if template is None else str(template)
        return re.sub(
            r'\{\{\s*([A-Za-z][A-Za-z0-9]*)\s*\}\}',
            lambda match: values.get(match.group(1), match.group(0)),
            text,
        )

    @classmethod
    def _build_filter_result(  # noqa: PLR0913
        cls,
        *,
        prompt: dict[str, Any],
        title: str,
        summary: str,
        body: str,
        source_name: str,
        published_time: Any,
        keep: bool,
        score: int,
        category: str,
        tags: list[str],
        reason: str,
        policy: dict[str, Any],
    ) -> dict[str, Any]:
        prompt_applied = bool(prompt)
        prompt_values = {
            'title': title,
            'body': body[:4000],
            'summary': summary[:1000],
            'source': source_name,
            'publishedAt': '' if published_time is None else str(published_time),
        }
        prompt_snapshot = {
            key: prompt.get(key)
            for key in (
                # Keep the immutable version identifier alongside the display
                # version number so the Worker can link its call to the exact
                # published prompt row in the backend audit trail.
                'promptId',
                'promptKey',
                'versionNo',
                'scene',
                'executionMode',
                'systemPrompt',
                'userPrompt',
                'ownerId',
                'collectionRunId',
                # This is a non-secret runtime snapshot.  It lets InsightHub
                # select the model configured in the admin console without
                # copying provider credentials into the inbox row.
                'modelRoute',
            )
            if prompt.get(key) is not None
        }
        return {
            'schema': 'pipesight-filter-v1',
            'mode': 'rule-based',
            'executionMode': 'rule-based' if not prompt_applied else 'rule-based-fallback',
            'promptApplied': prompt_applied,
            'promptKey': prompt.get('promptKey'),
            'promptVersionNo': prompt.get('versionNo'),
            'promptSnapshot': prompt_snapshot,
            'input': {
                'title': title,
                'summary': summary[:1000],
                'source': source_name,
                'publishedAt': prompt_values['publishedAt'],
                'bodyHash': hashlib.sha256(body.encode('utf-8')).hexdigest(),
                'renderedUserPrompt': cls._render_prompt(prompt.get('userPrompt'), prompt_values)[:6000]
                if prompt_applied
                else '',
            },
            'rulePolicy': policy,
            'decision': {
                'keep': keep,
                'score': score,
                'reason': reason,
                'category': category,
                'keywords': tags,
            },
            'keep': keep,
            'reason': reason,
            'fallback': {
                'used': True,
                'reason': (
                    '采集阶段按固定规则完成预过滤；InsightHub Worker 将继续执行'
                    '快照中的管理端提示词。'
                ),
            },
        }

    @classmethod
    def process_record(
        cls,
        record: dict[str, Any],
        *,
        source_type: str,
        source_name: str,
        filter_prompt: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        title = cls.normalize_text(record.get('title'))
        summary = cls.normalize_text(record.get('summary') or record.get('abstract'))
        body = cls.normalize_text(record.get('body') or record.get('content') or summary)
        canonical_url = cls.canonicalize_url(record.get('url') or record.get('canonical_url'))
        content = body or summary
        score, tags, category = cls._classification(title, f'{title} {summary} {body}', source_type)
        issues: list[str] = []
        if not title:
            issues.append('缺少标题')
        elif len(title) < cls.MIN_TITLE_LENGTH:
            issues.append('标题过短')
        if not canonical_url:
            issues.append('缺少规范化地址')
        if not content:
            issues.append('缺少正文或摘要')
        elif len(content) < cls.MIN_CONTENT_LENGTH:
            issues.append('正文或摘要过短')
        if not record.get('published_time') and source_type != 'paper':
            issues.append('缺少发布时间')
        mandatory_failure = any(issue in issues for issue in ('缺少标题', '缺少规范化地址')) or (
            '缺少正文或摘要' in issues and source_type != 'paper'
        )
        keep = not mandatory_failure and score >= cls.MIN_RELEVANCE_SCORE
        if not keep and not mandatory_failure:
            issues.append('未命中管网相关性规则')
        quality_score = max(0, 100 - len(issues) * 12)
        quality_status = 'fail' if mandatory_failure else 'warn' if issues else 'pass'
        status = 'rejected' if not keep else 'warning' if issues else 'accepted'
        prompt = filter_prompt or {}
        filter_reason = '；'.join(issues) if issues else '通过规范化、质量和管网相关性规则'
        filter_result = cls._build_filter_result(
            prompt=prompt,
            title=title,
            summary=summary,
            body=body,
            source_name=source_name,
            published_time=record.get('published_time'),
            keep=keep,
            score=score,
            category=category,
            tags=tags,
            reason=filter_reason,
            policy={
                'mandatoryFields': ['title', 'canonical_url', 'content'],
                'minimumTitleLength': cls.MIN_TITLE_LENGTH,
                'minimumContentLength': cls.MIN_CONTENT_LENGTH,
                'minimumRelevanceScore': cls.MIN_RELEVANCE_SCORE,
                'simhashDistanceThreshold': cls.SIMHASH_DISTANCE_THRESHOLD,
            },
        )
        quality = {'score': quality_score, 'status': quality_status, 'issues': issues}
        processing = {
            'version': cls.VERSION,
            'sourceName': source_name,
            'urlHash': hashlib.sha256(canonical_url.encode('utf-8')).hexdigest() if canonical_url else '',
            'contentHash': cls.content_hash(title, body, summary),
            'simhash': cls.simhash(f'{title}\n{content}'),
            'quality': quality,
            'classification': {'category': category, 'tags': tags, 'score': score},
            'filter': filter_result,
        }
        return {
            'keep': keep,
            'status': status,
            'title': title,
            'summary': summary[:1000],
            'body': body[:2_000_000],
            'canonical_url': canonical_url,
            'score': score,
            'category': category,
            'tags': tags,
            'quality': quality,
            'processing': processing,
        }
