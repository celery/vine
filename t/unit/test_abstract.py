from vine.abstract import Thenable
from vine.promises import promise


class CanThen:

    def then(self, x, y):
        pass


class CannotThen:
    pass


class test_Thenable:

    def test_isa(self):
        assert isinstance(CanThen(), Thenable)
        assert not isinstance(CannotThen(), Thenable)

    def test_promise(self):
        assert isinstance(promise(lambda x: x), Thenable)
