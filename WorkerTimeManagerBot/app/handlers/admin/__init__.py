from . import workers_management, logs_management
from . import sessions_management, sessions_editor
from ...misc.middlewares import AdminCheckMiddleware

admin_routers = [workers_management.router, sessions_management.router, sessions_editor.router, logs_management.router]


# Устанавливаем middleware для всех детей родительского класса админа
for router in admin_routers:
    router.message.middleware(AdminCheckMiddleware())
    router.callback_query.middleware(AdminCheckMiddleware())