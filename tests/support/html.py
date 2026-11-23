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


class _Elements(HTMLParser):
    def __init__(self, tag: str) -> None:
        super().__init__()
        self.tag = tag
        self.found: list[tuple[dict[str, str | None], str]] = []
        self._open = False

    def handle_starttag(self, tag, attrs):
        if tag == self.tag:
            self.found.append((dict(attrs), ""))
            self._open = True

    def handle_endtag(self, tag):
        if tag == self.tag:
            self._open = False

    def handle_data(self, data):
        if self._open:
            attrs, text = self.found[-1]
            self.found[-1] = (attrs, text + data)


def elements(page: str, tag: str) -> list[tuple[dict[str, str | None], str]]:
    """The attributes and text of every ``tag`` element that holds only text, in page order."""
    parser = _Elements(tag)
    parser.feed(page)
    parser.close()
    return [(attrs, text.strip()) for attrs, text in parser.found]
