from django.contrib import admin

from .models import Card, Game, Player, Round

# Register your models here.

admin.site.register(Card)
admin.site.register(Game)
admin.site.register(Player)
admin.site.register(Round)

