import hashlib
import json
import random
import time

from collections import Counter
from datetime import datetime, timedelta
from enum import IntEnum

from django.conf import settings
from django.core import validators
from django.core.exceptions import ObjectDoesNotExist
from django.db import models, transaction

from game.errors import *


class Card(models.Model):
    text = models.CharField(
        max_length=100,
    )
    is_black = models.BooleanField(
    )
    pick = models.PositiveSmallIntegerField(
        null=True,
    )

    def __str__(self):
        return 'Card(is_black={})'.format(self.is_black)

    def to_dict(self, auth_token=None):
        as_dict = {
            'id': self.id,
            'isBlack': self.is_black,
            'text': self.text,
        }
        if self.pick is not None:
            as_dict['pick'] = self.pick
        return as_dict

    @classmethod
    def create_card(cls, text, is_black):
        pick = text.count('_') if is_black else None
        return Card.objects.create(
            text=text,
            is_black=is_black,
            pick=pick,
        )


class Hand(models.Model):
    cards = models.ManyToManyField(
        Card,
        related_name='+',
    )

    def __str__(self):
        return 'Hand(cards={})'.format(
            list(self.cards.all())
        )


class Player(models.Model):
    name = models.CharField(
        max_length=32,
        validators=[
            validators.validate_unicode_slug,
        ],
    )
    auth_token = models.CharField(
        max_length=64,
        unique=True,
        validators=[
            validators.validate_slug,
            validators.MinLengthValidator(64),
        ],
    )
    current_game = models.ForeignKey(
        'Game',
        on_delete=models.SET_NULL,
        null=True,
    )
    current_hand = models.ForeignKey(
        Hand,
        on_delete=models.SET_NULL,
        null=True,
        related_name='+',
    )
    score = models.PositiveSmallIntegerField(
        null=True,
    )

    def __str__(self):
        return 'Player(name="{}", id={})'.format(self.name, self.id)

    def to_dict(self, auth_token=None):
        as_dict = {
            'id': self.id,
            'name': self.name
        }
        if auth_token == self.auth_token and self.current_hand is not None:
            as_dict['hand'] = list(map(
                lambda card: card.to_dict(),
                self.current_hand.cards.all()
            ))
        if self.score is not None:
            as_dict['score'] = self.score
        return as_dict

    def leave_current_game(self):
        if self.current_game is None:
            return
        game = self.current_game
        self.current_game.remove_player(self)
        game.save()

    @classmethod
    def create_new_player(cls, name):
        token = hashlib.sha256()
        token.update(name.encode('utf-8'))
        token.update(settings.SECRET_KEY.encode('utf-8'))
        token.update(str(time.time()).encode('utf-8'))
        token = token.hexdigest()

        new_player = Player.objects.create(name=name, auth_token=token)

        return new_player

    @classmethod
    def get_players_by_ids(cls, ids, *related_fields):
        players = Player.objects
        if len(related_fields) != 0:
            players = players.select_related(*related_fields)
        return players.filter(pk__in=ids)

    @classmethod
    def get_player_by_token(cls, token, *related_fields, lock=True):
        players = Player.objects
        if len(related_fields):
            players = players.select_related(*related_fields)
        if lock:
            players = players.select_for_update()
        return players.get(auth_token=token)

    @classmethod
    def create_game(cls, auth_token):
        with transaction.atomic():
            player = Player.get_player_by_token(auth_token, 'current_game')
            player.leave_current_game()

            new_game = Game.objects.create(host=player)
            new_game.add_player(player)
            new_game.save()

            player.save()

            return new_game

    @classmethod
    def start_game(cls, auth_token):
        with transaction.atomic():
            player = Player.get_player_by_token(auth_token, 'current_game')
            game = player.current_game
            game.start_by(player)
            game.save()

    @classmethod
    def join_game(cls, auth_token, game_id):
        with transaction.atomic():
            player = Player.get_player_by_token(auth_token, 'current_game')
            if player.current_game is not None \
                    and player.current_game.id == game_id:
                return
            player.leave_current_game()

            game = Game.objects.select_for_update().get(pk=game_id)
            game.add_player(player)
            game.save()

            player.save()

    @classmethod
    def leave_game(cls, auth_token):
        with transaction.atomic():
            player = Player.get_player_by_token(auth_token, 'current_game')

            if player.current_game is None:
                raise PlayerNotInGameError()

            player.leave_current_game()

            player.save()

    @classmethod
    def play_card(cls, auth_token, card_id):
        with transaction.atomic():
            player = Player.get_player_by_token(
                auth_token,
                'current_game',
                'current_game__current_round',
            )

            if player.current_game is None:
                raise PlayerNotInGameError()

            try:
                card = Card.objects.get(id=card_id),
            except ObjectDoesNotExist:
                raise CardDoesNotExistError()

            player.current_game.play_card(
                player,
                Card.objects.get(id=card_id),
                datetime.now(),
            )
            player.current_game.save()
            player.save()


class Deque(models.Model):
    cards = models.TextField(
        default='[]',
    )
    deque = models.TextField(
        default='[]',
    )
    size = models.PositiveSmallIntegerField(
        default=0,
    )

    def __str__(self):
        return 'Deque(id={}, size={})'.format(
            self.id,
            self.size,
        )

    def _get_deque(self):
        return json.loads(self.deque)

    def _set_deque(self, cards):
        self.deque = json.dumps(cards)

    def _get_cards(self):
        return json.loads(self.cards)

    def _set_cards(self, cards):
        self.cards = json.dumps(cards)

    def _remove_cards(self, cards_to_remove):
        def try_pop(counter, element):
            if element not in counter:
                return False
            counter[element] -= 1
            if counter[element] == 0:
                del counter[element]
            return True

        cards_to_remove = Counter(cards_to_remove)
        current_cards = self._get_cards()
        num_cards_to_remove = len(cards_to_remove)
        new_cards = [
            card
            for card in current_cards
            if not try_pop(cards_to_remove, card)
        ]
        if len(cards_to_remove) != 0:
            raise CardNotInDequeError()
        self.size -= num_cards_to_remove
        self._set_cards(new_cards)

    def add_cards(self, new_cards):
        self.size += len(new_cards)
        self._set_cards(self._get_cards() + list(new_cards))

    def shuffle(self):
        new_deque = self._get_cards()
        random.shuffle(new_deque)
        self._set_deque(new_deque)

    def draw_single_card(self):
        return self.draw_cards(1)

    def draw_cards(self, num_cards):
        if num_cards > self.size:
            raise NotEnoughCardsError()

        deque = self._get_deque()

        if len(deque) > num_cards:
            drawn_cards = deque[:num_cards]
            self._remove_cards(drawn_cards)
            self._set_deque(deque[num_cards:])
            return drawn_cards

        drawn_cards = deque[:]
        self._remove_cards(drawn_cards)
        self.shuffle()

        if len(drawn_cards) < num_cards:
            drawn_cards += self.draw_cards(num_cards - len(drawn_cards))

        return drawn_cards


class Queue(models.Model):
    items = models.TextField(
        default='[]',
    )

    def _get_items(self):
        return json.loads(self.items)

    def _set_items(self, items):
        self.items = json.dumps(items)

    def add_item(self, item):
        items = self._get_items()
        items.append(item)
        self._set_items(items)

    def pop_item(self):
        items = self._get_items()
        if len(items) == 0:
            return None
        popped_item = items[0]
        items = items[1:]
        self._set_items(items)
        return popped_item

    def remove_item(self, item):
        items = self._get_items()
        items = [i for i in items if i != item]
        self._set_items(items)


class Game(models.Model):
    MIN_PLAYERS = 3
    MAX_PLAYERS = 10

    HAND_SIZE = 10

    PLAY_PHASE_LENGTH_SECONDS = 300
    PICK_PHASE_LENGTH_SECONDS = 300
    FINISH_DELAY_SECONDS = 1

    WINNER_SCORE = 3

    Status = models.TextChoices('Status', 'CREATED STARTED FINISHED')

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.CREATED,
    )
    host = models.ForeignKey(
        'Player',
        on_delete=models.CASCADE,
        null=True,
        related_name='+',
    )
    current_round = models.ForeignKey(
        'Round',
        on_delete=models.SET_NULL,
        null=True,
        related_name='+',
    )
    black_deque = models.ForeignKey(
        Deque,
        on_delete=models.CASCADE,
        related_name='+',
        null=True,
    )
    white_deque = models.ForeignKey(
        Deque,
        on_delete=models.CASCADE,
        related_name='+',
        null=True,
    )
    player_queue = models.ForeignKey(
        Queue,
        on_delete=models.CASCADE,
        related_name='+',
        null=True,
    )

    def to_dict(self, auth_token=None):
        self._update_state()

        as_dict = {
            'id': self.id,
            'players': list(map(
                lambda player: player.to_dict(auth_token=auth_token),
                self.player_set.all()
            )),
            'status': self.status,
        }
        if self.current_round is not None:
            as_dict['cardCzarId'] = self.current_round.card_czar.id
            as_dict['blackCard'] = self.current_round.black_card.to_dict()
            if self.current_round.get_state() > Round.State.PLAY:
                as_dict['whiteCards'] = list(map(
                    lambda turn: turn.card.to_dict(auth_token=auth_token),
                    self.current_round.turn_set.all()
                ))
        if self.host is not None:
            as_dict['hostId'] = self.host.id
        return as_dict

    def _get_winner(self):
        winner = self.player_set.filter(score=Game.WINNER_SCORE)
        if winner.count() == 0:
            return None
        return winner.get()

    def _update_state(self):
        if self.player_queue is None:
            self.player_queue = Queue.objects.create()
            self.player_queue.save()

        if self.status == Game.Status.STARTED \
                and self.current_round is not None \
                and self.current_round.get_state() == Round.State.FINISHED:
            winner = self._get_winner()
            if winner is not None:
                self.status = Game.Status.FINISHED
                return
            self._start_new_round()

        if self.black_deque is None:
            black_cards = list(
                Card
                    .objects
                    .filter(is_black=True)
                    .values_list('id', flat=True)
            )
            self.black_deque = Deque.objects.create()
            self.black_deque.add_cards(black_cards)
            self.black_deque.shuffle()
            self.black_deque.save()

        if self.white_deque is None:
            white_cards = list(
                Card
                    .objects
                    .filter(is_black=False)
                    .values_list('id', flat=True)
            )
            self.white_deque = Deque.objects.create()
            self.white_deque.add_cards(white_cards)
            self.white_deque.shuffle()
            self.white_deque.save()

        self.save()

    def _repick_host(self):
        self.host = self.player_set.first()

    def _deal_cards_to_player(self, player):
        if player.current_hand is None:
            player.current_hand = Hand.objects.create()
            player.save()

        num_cards_in_hand = player.current_hand.cards.count()
        num_cards_to_deal = Game.HAND_SIZE - num_cards_in_hand
        if num_cards_to_deal == 0:
            return

        new_card_ids = self.white_deque.draw_cards(num_cards_to_deal)
        self.white_deque.save()
        player.current_hand.cards.add(
            *Card.objects.filter(id__in=new_card_ids)
        )
        player.current_hand.save()

    def _deal_cards(self):
        for player in self.player_set.all():
            self._deal_cards_to_player(player)

    def _draw_black_card(self):
        card_id = self.black_deque.draw_single_card()[0]
        self.black_deque.save()
        return Card.objects.get(id=card_id)

    def _start_new_round(self):
        if self.status == Game.Status.FINISHED:
            raise GameFinishedError()
        if self.status == Game.Status.CREATED:
            self.status = Game.Status.STARTED

        now = datetime.now()

        play_finish = now \
                + timedelta(seconds=Game.PLAY_PHASE_LENGTH_SECONDS)
        pick_finish = play_finish \
                + timedelta(seconds=Game.PICK_PHASE_LENGTH_SECONDS)
        round_finish = pick_finish \
                + timedelta(seconds=Game.FINISH_DELAY_SECONDS)

        card_czar_id = self.player_queue.pop_item()
        card_czar = self.player_set.filter(id=card_czar_id).get()
        self.player_queue.add_item(card_czar_id)
        self.player_queue.save()
        print('czar:', card_czar_id)
        print('queue:', self.player_queue.items)

        self.current_round = Round.objects.create(
            game=self,
            card_czar=card_czar,
            black_card=self._draw_black_card(),
            play_finish=play_finish,
            pick_finish=pick_finish,
            round_finish=round_finish,
        )

        self._deal_cards()

        self.save()

    def _pick_card(self, card, asof):
        round = self.current_round
        turn = round.turn_set.filter(card=card)
        if turn.count() == 0:
            raise CardIsNotOnTableError()
        turn = turn.get()
        if turn.player.current_game == self:
            turn.player.score += 1
        round.pick_finish = asof
        round.round_finish = asof + \
                timedelta(seconds=Game.FINISH_DELAY_SECONDS)

        turn.player.save()
        round.save()

    def _play_card(self, player, card, asof):
        if player.current_hand is None \
                or player.current_hand.cards.filter(id=card.id).count() == 0:
            raise PlayerDoesNotHaveCardError()

        self.current_round.play_card(player, card)
        if self.current_round.turn_set.count() + 1 == self.player_set.count():
            self.current_round.play_finish = asof
            self.current_round.pick_finish = asof \
                    + timedelta(seconds=Game.PICK_PHASE_LENGTH_SECONDS)
            self.current_round.round_finish = asof \
                    + timedelta(seconds=Game.FINISH_DELAY_SECONDS)

        self.current_round.save()

    def start_by(self, player):
        self._update_state()

        if self.status == Game.Status.FINISHED:
            raise GameFinishedError()
        if self.host != player:
            raise PermissionDeniedError()
        if self.player_set.count() < Game.MIN_PLAYERS:
            raise NotEnoughPlayersError()

        self._start_new_round()

    def play_card(self, player, card, asof):
        self._update_state()

        if self.status == Game.Status.FINISHED:
            raise GameFinishedError()
        if self.status == Game.Status.CREATED:
            raise GameNotStartedError()

        round_state = self.current_round.get_state(asof)
        if player == self.current_round.card_czar:
            if round_state != Round.State.PICK:
                raise PermissionDeniedError()
            self._pick_card(card, asof)
        else:
            if round_state != Round.State.PLAY:
                raise PermissionDeniedError()
            self._play_card(player, card, asof)

    def add_player(self, player):
        self._update_state()

        if self.status == Game.Status.FINISHED:
            raise GameFinishedError()
        if self.player_set.count() == Game.MAX_PLAYERS:
            raise GameIsFullError()
        self.player_queue.add_item(player.id)
        self.player_queue.save()

        self.player_set.add(player)
        self._deal_cards_to_player(player)
        player.score = 0
        player.save()

    def remove_player(self, player):
        self._update_state()

        self.player_queue.remove_item(player.id)
        self.player_queue.save()

        player.current_game = None
        player.current_hand = None
        player.score = None

        player.save()

        if self.player_set.count() == 0:
            self.host = None
            self.status = Game.Status.FINISHED
            self.current_round = None
            return

        if player == self.host:
            self._repick_host()

        if self.current_round is not None:
            round = self.current_round
            if player == round.card_czar \
                    and round.get_state() <= round.State.PICK:
                self._start_new_round()
            else:
                round.remove_player(player)
            round.save()


class Round(models.Model):
    class State(IntEnum):
        PLAY = 1
        PICK = 2
        WAITING_FINISH = 3
        FINISHED = 4

    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name='+',
    )
    card_czar = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='+',
    )
    black_card = models.ForeignKey(
        Card,
        on_delete=models.CASCADE,
        related_name='+',
    )
    play_finish = models.DateTimeField(
    )
    pick_finish = models.DateTimeField(
    )
    round_finish = models.DateTimeField(
    )

    def get_state(self, asof=None):
        if asof is None:
            asof = datetime.now()
        if asof <= self.play_finish:
            return Round.State.PLAY
        if asof <= self.pick_finish:
            return Round.State.PICK
        if asof <= self.round_finish:
            return Round.State.WAITING_FINISH
        return Round.State.FINISHED

    def play_card(self, player, card):
        if self.turn_set.filter(player=player).count() > 0:
            raise PlayerHasAlreadyPlayed()
        Turn.objects.create(
            round=self,
            player=player,
            card=card,
        )

    def remove_player(self, player):
        player_turn = self.turn_set.filter(player=player)
        if player_turn.count() == 0:
            return
        player_turn = player_turn.get()
        self.turn_set.remove(player_turn, bulk=False)
        player_turn.save()


class Turn(models.Model):
    round = models.ForeignKey(
        Round,
        on_delete=models.CASCADE,
    )
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='+',
    )
    card = models.ForeignKey(
        Card,
        on_delete=models.CASCADE,
        null=True,
        related_name='+',
    )

