from .user import start, work
from .state import user_states, admin_states
from .admin import admin_routers

# Список из роутеров: здесь очень важно не менять порядок (а лучше и вовсе ничего не трогать)
routers = [start.router, admin_states.router, user_states.router, *admin_routers, work.router]