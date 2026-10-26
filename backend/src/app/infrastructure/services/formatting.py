"""基础设施层的展示格式化能力。"""


def format_bytes(value: int, format_string: str = '%(value).1f%(symbol)s') -> str:
    """将字节数格式化为适合展示的文本。"""
    symbols = ('B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB')
    prefixes = {symbol: 1 << (index + 1) * 10 for index, symbol in enumerate(symbols[1:])}
    for symbol in reversed(symbols[1:]):
        if value >= prefixes[symbol]:
            return format_string % {'value': float(value) / prefixes[symbol], 'symbol': symbol}
    return format_string % {'value': value, 'symbol': symbols[0]}
