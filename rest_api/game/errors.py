class CAHError(Exception):
    def __str__(self):
        return type(self).__name__


class GameIsFullError(CAHError):
    pass


class GameFinishedError(CAHError):
    pass


class GameNotStartedError(CAHError):
    pass


class NotEnoughPlayersError(CAHError):
    pass


class PlayerNotInGameError(CAHError):
    pass


class PermissionDeniedError(CAHError):
    pass


class NotEnoughCardsError(CAHError):
    pass


class CardNotInDequeError(CAHError):
    pass


class CardDoesNotExistError(CAHError):
    pass


class CardIsNotOnTableError(CAHError):
    pass


class PlayerDoesNotHaveCardError(CAHError):
    pass

class PlayerHasAlreadyPlayed(CAHError):
    pass

