from html.parser import HTMLParser


class _Alerts(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.texts: list[str] = []
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        if self._depth:
            self._depth += 1
        elif dict(attrs).get("role") == "alert":
            self._depth = 1
            self.texts.append("")

    def handle_endtag(self, tag):
        if self._depth:
            self._depth -= 1

    def handle_data(self, data):
        if self._depth:
            self.texts[-1] += data


def alert_texts(page: str) -> list[str]:
    """The text of every element with role="alert", as a reader would see it."""
    parser = _Alerts()
    parser.feed(page)
    parser.close()
    return [text.strip() for text in parser.texts]
