from django.conf import settings
from django.http import HttpResponseServerError, HttpResponseBadRequest, HttpResponse, JsonResponse

from game.errors import CAHError
from game.models import Game, Player


def screen_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except CAHError as e:
            return HttpResponseServerError(str(e))
        # except Exception as e:
        #     if settings.DEBUG:
        #         return HttpResponseServerError(str(e))
        #     return HttpResponseServerError()
    return wrapper


def returns_success(func):
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
            return JsonResponse({'success': True})
        except CAHError as e:
            return JsonResponse({
                'success': False,
                'errorMessage': str(e)
            })
        # except Exception as e:
        #     if settings.DEBUG:
        #         return HttpResponseServerError(str(e))
        #     return HttpResponseServerError()
    return wrapper


@screen_errors
def add_player(request):
    name = request.GET.get('name')

    new_player = Player.create_new_player(name)
    result = new_player.auth_token
    return HttpResponse(result)


@screen_errors
def get_players_by_ids(request):
    ids = request.GET.get('ids')
    ids = [int(id) for id in ids.split(',')]

    if len(ids) > 20:
        return HttpResponseBadRequest('Got more than 20 ids')

    players = Player.get_players_by_ids(ids)
    result = [player.to_dict() for player in players]
    return JsonResponse(result, safe=False)


@screen_errors
def get_player_by_token(request):
    token = request.GET.get('authToken')

    player = Player.get_player_by_token(token, lock=False)
    result = player.to_dict(auth_token=token)
    return JsonResponse(result)


@screen_errors
def create_game(request):
    token = request.GET.get('authToken')

    new_game = Player.create_game(token)
    result = new_game.id
    return HttpResponse(result)


@screen_errors
def get_game(request):
    token = request.GET.get('authToken')
    game_id = request.GET.get('id')

    game = Game.objects.select_related(
        'current_round',
    ).get(id=game_id)
    result = game.to_dict(auth_token=token)
    return JsonResponse(result)


@returns_success
def join_game(request):
    token = request.GET.get('authToken')
    game_id = request.GET.get('id')

    Player.join_game(token, game_id)


@returns_success
def play_card(request):
    token = request.GET.get('authToken')
    card_id = request.GET.get('id')

    Player.play_card(token, card_id)


@returns_success
def start_game(request):
    token = request.GET.get('authToken')

    Player.start_game(token)


@returns_success
def leave_game(request):
    token = request.GET.get('authToken')

    Player.leave_game(token)

