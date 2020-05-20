from django.urls import path

from . import views


urlpatterns = [
    path('players/add', views.add_player),
    path('players/getByIds', views.get_players_by_ids),
    path('players/getMe', views.get_player_by_token),
    path('games/create', views.create_game),
    path('games/get', views.get_game),
    path('games/join', views.join_game),
    path('games/playCard', views.play_card),
    path('games/start', views.start_game),
    path('games/leave', views.leave_game),
]

