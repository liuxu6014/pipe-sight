"""资料文件的本地解析与安全路径策略。

该模块只负责文件内容处理，不负责数据库事务或 HTTP 编排。数据库资料服务
可以复用这里的纯文件能力，避免把解析细节继续堆到科研任务服务中。
"""

from __future__ import annotations

import asyncio
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from app.business_ids import wire_id
from app.business_time import format_business_time
from app.library.models.materials import PipelineMaterial
from app.library.repositories.material_repository import MaterialDao
from app.system.services.file_scan import FileScanService
from config.env import UploadConfig
from exceptions.exception import ServiceException

if TYPE_CHECKING:
    pass


class MaterialFileService:
    """资料文件的解析、摘要和上传目录边界校验。"""

    local_parser_extensions = frozenset({'.txt', '.md', '.docx', '.pdf'})
    external_parser_extensions = frozenset({'.pdf', '.doc'})
    max_source_bytes = 16 * 1024 * 1024
    max_extracted_chars = 2_000_000
    max_archive_entries = 2_000
    max_archive_uncompressed_bytes = 32 * 1024 * 1024
    max_pdf_pages = 500

    @classmethod
    def extract_plain_text(cls, local_path: str | None, original_name: str) -> str:
        if not local_path:
            return ''
        suffix = Path(original_name).suffix.lower()
        try:
            if suffix in {'.txt', '.md'}:
                return cls._extract_text_file(Path(local_path))
            if suffix == '.docx':
                return cls._extract_docx_text(Path(local_path))
            if suffix == '.pdf':
                return cls._extract_pdf_text(Path(local_path))
        except (OSError, ValueError, zipfile.BadZipFile, ET.ParseError, KeyError, PyPdfError):
            return ''
        return ''

    @classmethod
    def _extract_text_file(cls, source: Path) -> str:
        with source.open('rb') as source_file:
            raw = source_file.read(cls.max_source_bytes + 1)
        raw = raw[: cls.max_source_bytes]
        encodings = (
            ['utf-8-sig', 'utf-16']
            if raw.startswith((b'\xef\xbb\xbf', b'\xff\xfe', b'\xfe\xff'))
            else ['utf-8', 'gb18030']
        )
        for encoding in encodings:
            try:
                return raw.decode(encoding).strip()[: cls.max_extracted_chars]
            except UnicodeDecodeError:  # noqa: PERF203
                continue
        return raw.decode('utf-8', errors='replace').strip()[: cls.max_extracted_chars]

    @classmethod
    def _extract_docx_text(cls, source: Path) -> str:
        word_namespace = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        paragraph_tag = f'{{{word_namespace}}}p'
        text_tag = f'{{{word_namespace}}}t'
        tab_tag = f'{{{word_namespace}}}tab'
        break_tags = {f'{{{word_namespace}}}br', f'{{{word_namespace}}}cr'}
        with zipfile.ZipFile(source) as archive:
            cls._validate_docx_archive(archive)
            document_info = archive.getinfo('word/document.xml')
            if document_info.file_size > cls.max_source_bytes:
                raise ValueError('DOCX document.xml exceeds the local parser limit')
            document_root = ET.fromstring(archive.read(document_info))

        paragraphs: list[str] = []
        extracted_chars = 0
        for paragraph in document_root.iter(paragraph_tag):
            fragments: list[str] = []
            for node in paragraph.iter():
                if node.tag == text_tag and node.text:
                    fragments.append(node.text)
                elif node.tag == tab_tag:
                    fragments.append('\t')
                elif node.tag in break_tags:
                    fragments.append('\n')
            paragraph_text = ''.join(fragments).strip()
            if not paragraph_text:
                continue
            remaining = cls.max_extracted_chars - extracted_chars
            if remaining <= 0:
                break
            paragraphs.append(paragraph_text[:remaining])
            extracted_chars += min(len(paragraph_text), remaining) + 1
        return '\n'.join(paragraphs).strip()

    @classmethod
    def _validate_docx_archive(cls, archive: zipfile.ZipFile) -> None:
        """在读取 XML 前限制 DOCX ZIP 的条目数和解压后总大小。"""
        entries = archive.infolist()
        if len(entries) > cls.max_archive_entries:
            raise ValueError('DOCX contains too many archive entries')
        total_uncompressed_bytes = sum(max(info.file_size, 0) for info in entries)
        if total_uncompressed_bytes > cls.max_archive_uncompressed_bytes:
            raise ValueError('DOCX expanded content exceeds the local parser limit')

    @classmethod
    def _extract_pdf_text(cls, source: Path) -> str:
        if source.stat().st_size > cls.max_source_bytes:
            raise ValueError('PDF exceeds the local parser limit')
        reader = PdfReader(str(source))
        if reader.is_encrypted and not reader.decrypt(''):
            raise ValueError('encrypted PDF requires a password')
        if len(reader.pages) > cls.max_pdf_pages:
            raise ValueError(f'PDF exceeds the local page limit of {cls.max_pdf_pages}')
        pages: list[str] = []
        extracted_chars = 0
        for page in reader.pages:
            page_text = (page.extract_text() or '').strip()
            if not page_text:
                continue
            remaining = cls.max_extracted_chars - extracted_chars
            if remaining <= 0:
                break
            pages.append(page_text[:remaining])
            extracted_chars += min(len(page_text), remaining) + 2
        return '\n\n'.join(pages).strip()

    @classmethod
    def safe_local_path(cls, file_path: str | None) -> Path | None:
        """将数据库中的上传路径解析到上传根目录内，拒绝目录穿越。"""
        if not file_path:
            return None
        upload_root = Path(UploadConfig.UPLOAD_PATH).resolve()
        normalized = file_path.replace('\\', '/')
        prefix = UploadConfig.UPLOAD_PREFIX.rstrip('/')
        if normalized == prefix or normalized.startswith(f'{prefix}/'):
            candidate = upload_root / normalized[len(prefix) :].lstrip('/')
        else:
            candidate = Path(file_path) if Path(file_path).is_absolute() else upload_root / file_path
        resolved = candidate.resolve()
        try:
            resolved.relative_to(upload_root)
        except ValueError:
            return None
        return resolved

    @classmethod
    def summarize(cls, text: str, limit: int = 220) -> str:
        compact = re.sub(r'\s+', ' ', text or '').strip()
        return compact if len(compact) <= limit else f'{compact[:limit].rstrip()}…'

    @classmethod
    def parse(
        cls,
        local_path: str | None,
        original_name: str,
        *,
        requested_at: str,
        extractor: Any | None = None,
    ) -> tuple[str, str, str, dict[str, Any]]:
        suffix = Path(original_name).suffix.lower()
        if suffix == '.doc':
            return (
                'failed',
                '暂不支持旧版 DOC，请先另存为 DOCX 或 PDF 后重新上传。',
                '',
                {'parser': 'unsupported-doc', 'lastParseAt': requested_at},
            )
        if suffix not in cls.local_parser_extensions:
            return (
                'queued',
                '文件已安全保存，当前文件类型需要外部解析器处理。',
                '',
                {'parser': 'queued-external-parser', 'lastParseRequestedAt': requested_at},
            )
        if not local_path or not Path(local_path).is_file():
            return (
                'failed',
                '源文件不存在，无法执行基础文本解析。',
                '',
                {'parser': 'local-basic-parser', 'lastParseAt': requested_at},
            )

        extracted_text = (extractor or cls.extract_plain_text)(local_path, original_name)
        parser = {'.docx': 'docx-ooxml', '.pdf': 'pypdf'}.get(suffix, 'plain-text')
        if not extracted_text:
            empty_message = (
                'PDF 未提取到可检索文字，文件可能为扫描版、已加密或已损坏；请转换为可搜索 PDF 或 DOCX 后重试。'
                if suffix == '.pdf'
                else '基础解析未提取到有效正文，请检查文件内容后重试。'
            )
            return (
                'failed',
                empty_message,
                '',
                {'parser': parser, 'lastParseAt': requested_at, 'contentLength': 0},
            )
        truncated = len(extracted_text) >= cls.max_extracted_chars
        message = (
            'PDF 已完成文本提取，可用于关键词检索。' if suffix == '.pdf' else '文本已完成基础提取，可用于关键词检索。'
        )
        if truncated:
            message = f'{message}正文超过本地解析上限，已保留前 {cls.max_extracted_chars} 个字符。'
        return (
            'ready',
            message,
            extracted_text,
            {
                'parser': parser,
                'lastParseAt': requested_at,
                'contentLength': len(extracted_text),
                'truncated': truncated,
            },
        )


class MaterialService:
    """私有资料事务。扫描结果不另加旧实体列；解析/下载每次执行安全门。"""

    @staticmethod
    def effective_text(item):
        return item.edited_text if item.edited_text is not None else (item.extracted_text or '')

    @classmethod
    def material_dict(cls, item, viewer_user_id=None, **_):
        import hashlib
        text = cls.effective_text(item)
        return {
            'id': wire_id(item.id),
            'name': item.name,
            'fileName': item.filename,
            'fileSize': item.size,
            'fileHash': item.hash,
            'editHash': hashlib.sha256(item.edited_text.encode('utf-8')).hexdigest() if item.edited_text is not None else None,
            'format': Path(item.filename).suffix.lstrip('.').upper(),
            'type': '内部文献',
            'permissionScope': 'private',
            'permission': '仅自己可见',
            'ownerId': item.user_id,
            'owner': '',
            'canManage': viewer_user_id == item.user_id,
            'parseStatus': item.status,
            'status': {'queued': '等待解析', 'parsing': '解析中', 'ready': '已解析', 'failed': '解析失败'}.get(
                item.status, item.status
            ),
            'parseMessage': item.error or '',
            'summary': MaterialFileService.summarize(text),
            'version': f'V{item.version}.0',
            'versionNo': item.version,
            'tags': [],
            'keywords': [],
            'updatedAt': format_business_time(item.updated_at),
            'createdAt': format_business_time(item.created_at),
        }

    @classmethod
    def material_detail_dict(cls, item, viewer_user_id=None, **kwargs):
        return {
            **cls.material_dict(item, viewer_user_id, **kwargs),
            'extractedText': item.extracted_text or '',
            'editedText': item.edited_text,
            'content': cls.effective_text(item),
            'contentLength': len(cls.effective_text(item)),
            'hasExtractedText': bool(item.extracted_text),
        }

    @classmethod
    async def list_materials(cls, db, user_id, **kwargs):
        rows = await MaterialDao.list_accessible_materials(db, user_id)
        return {'rows': [cls.material_dict(i, user_id, **kwargs) for i in rows], 'total': len(rows)}

    @classmethod
    async def get_material(cls, db, user_id, material_id, **kwargs):
        row = await MaterialDao.get_owned_material(db, material_id, user_id)
        if not row:
            raise ServiceException(message='资料不存在或无权访问')
        return cls.material_detail_dict(row, user_id, **kwargs)

    @staticmethod
    async def get_download(db, user_id, material_id, *, local_path_resolver=MaterialFileService.safe_local_path):
        row = await MaterialDao.get_owned_material(db, material_id, user_id)
        if not row:
            raise ServiceException(message='资料不存在或无权访问')
        path = local_path_resolver(row.storage_key)
        if not path or not path.is_file():
            raise ServiceException(message='文件已失效')
        scan = await asyncio.to_thread(FileScanService.scan, str(path), row.filename)
        if scan.status != 'clean':
            raise ServiceException(message='资料未通过安全扫描，暂不可下载')
        return path, row.filename, row.mime_type

    @staticmethod
    def detect_mime(path, name):
        suffix = Path(name).suffix.lower()
        if path.stat().st_size > MaterialFileService.max_source_bytes:
            raise ServiceException(message='资料超过大小限制')
        with path.open('rb') as source:
            header = source.read(1024)
        if suffix == '.pdf' and header.startswith(b'%PDF-'):
            return 'application/pdf'
        if suffix == '.docx' and zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                MaterialFileService._validate_docx_archive(archive)
                archive.getinfo('word/document.xml')
            return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        if suffix in {'.txt', '.md'} and b'\x00' not in header and not header.startswith((b'MZ', b'\x7fELF')):
            # 确认可解码文本，不只相信上传 MIME。
            import codecs

            try:
                codecs.getincrementaldecoder('utf-8-sig')().decode(header, final=False)
            except UnicodeDecodeError:
                codecs.getincrementaldecoder('gb18030')().decode(header, final=False)
            return 'text/markdown' if suffix == '.md' else 'text/plain'
        raise ServiceException(message='文件类型与内容不匹配或暂不支持')

    @classmethod
    async def create_material(
        cls,
        db,
        *,
        user_id,
        owner_name='',
        name,
        permission_scope='private',
        file_name=None,
        file_path=None,
        local_path=None,
        scanner=FileScanService.scan,
        detail_serializer=None,
        **kwargs,
    ):
        import hashlib

        if permission_scope != 'private':
            raise ServiceException(message='上传资料默认私有，暂不支持公开共享')
        path = MaterialFileService.safe_local_path(local_path or file_path)
        if not path or not path.is_file():
            raise ServiceException(message='上传文件不存在或路径越界')
        try:
            mime = await asyncio.to_thread(cls.detect_mime, path, name)
        except (ValueError, UnicodeError, KeyError, zipfile.BadZipFile):
            raise ServiceException(message='文件内容校验失败') from None
        scan = await asyncio.to_thread(scanner, str(path), name)
        from app.library.models.materials import utcnow

        file_hash = await asyncio.to_thread(lambda: hashlib.sha256(path.read_bytes()).hexdigest())
        if scan.status == 'clean':
            existing = await MaterialDao.find_duplicate_upload(db, user_id, file_hash)
            existing_path = MaterialFileService.safe_local_path(existing.storage_key) if existing else None
            if existing and existing_path and existing_path.is_file():
                if existing.status == 'failed':
                    existing.status, existing.error, existing.updated_at = 'queued', None, utcnow()
                await db.commit()
                # Only the new, redundant upload copy is disposable. Never unlink
                # the original, even if a caller passed its path directly.
                if path.resolve() != existing_path.resolve():
                    try:
                        await asyncio.to_thread(path.unlink)
                    except OSError:
                        pass
                return {**(detail_serializer or cls.material_detail_dict)(existing, user_id), 'duplicate': True}

        row = PipelineMaterial(
            user_id=user_id,
            name=name,
            filename=name,
            storage_key=str(path.relative_to(Path(UploadConfig.UPLOAD_PATH).resolve())),
            mime_type=mime,
            size=path.stat().st_size,
            hash=file_hash,
            status='queued' if scan.status == 'clean' else 'failed',
            error=None if scan.status == 'clean' else '资料未通过安全扫描，请配置扫描器后重试',
            extracted_text=None,
            edited_text=None,
            version=1,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        await MaterialDao.add_material(db, row)
        await db.commit()
        return (detail_serializer or cls.material_detail_dict)(row, user_id)

    @classmethod
    async def retry_parse(cls, db, user_id, material_id, **kwargs):
        row = await MaterialDao.get_owned_material(db, material_id, user_id, lock=True)
        if not row:
            raise ServiceException(message='资料不存在或无权解析')
        if row.status in {'parsing', 'queued'}:
            return cls.material_detail_dict(row, user_id)
        row.status, row.error = 'queued', None
        from app.library.models.materials import utcnow

        row.updated_at = utcnow()
        # 重解析不清空提取结果，更不修改 edited_text。
        await db.commit()
        return cls.material_detail_dict(row, user_id)

    @classmethod
    async def edit(cls, db, user_id, material_id, *, expected_version, edited_text, name=None):
        row = await MaterialDao.get_owned_material(db, material_id, user_id, lock=True)
        if not row or row.version != expected_version:
            raise ServiceException(message='资料不存在、无权访问或版本已变化')
        # 解析中的更新时间用作令牌，编辑时先取消该尝试并重新排队。
        if row.status == 'parsing':
            row.status = 'queued'
        row.edited_text = edited_text
        if name is not None:
            if not name.strip():
                raise ServiceException(message='资料名不能为空')
            row.name = name.strip()
        row.version += 1
        from app.library.models.materials import utcnow

        row.updated_at = utcnow()
        await db.commit()
        return cls.material_detail_dict(row, user_id)

    @staticmethod
    async def delete_material(db, user_id, material_id, **kwargs):
        row = await MaterialDao.get_owned_material(db, material_id, user_id, lock=True)
        if not row:
            raise ServiceException(message='资料不存在或无权删除')
        # 普通删除仅删除原件/篮关系；历史生成快照仍保留，明确返回策略。
        path = MaterialFileService.safe_local_path(row.storage_key)
        await db.delete(row)
        await db.commit()
        deleted = False
        if path and path.is_file():
            try:
                path.unlink()
                deleted = True
            except OSError:
                pass
        return {
            'id': wire_id(material_id),
            'deleted': True,
            'fileDeleted': deleted,
            'historicalSnapshotsRetained': True,
        }


class MaterialApiService:
    permission_labels = {'private': '仅自己可见'}
    parse_labels = {'queued': '等待解析', 'parsing': '解析中', 'ready': '已解析', 'failed': '解析失败'}
    permission_scopes = frozenset({'private'})
    _material_detail_dict = MaterialService.material_detail_dict
    _material_local_path = MaterialFileService.safe_local_path
    list_materials = MaterialService.list_materials
    get_material = MaterialService.get_material
    get_download = MaterialService.get_download
    create_material = MaterialService.create_material
    retry_parse = MaterialService.retry_parse
    delete_material = MaterialService.delete_material
    edit = MaterialService.edit

    @staticmethod
    def _parse_material_file(local_path, original_name):
        return MaterialFileService.parse(local_path, original_name, requested_at=datetime.now().isoformat())
