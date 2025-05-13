from vine.abstract import Thenable
from vine.promises import promise


class CanThen:

    def then(self, x, y):
        pass


class CannotThen:
    pass


def test_isa():
    assert isinstance(CanThen(), Thenable)
    assert not isinstance(CannotThen(), Thenable)


def test_promise():
    assert isinstance(promise(lambda x: x), Thenable)
