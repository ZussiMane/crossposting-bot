from telethon import TelegramClient

# Ваши данные API (из .env файла)
api_id = input("Введите API ID: ")
api_hash = input("Введите API Hash: ")
session_name = 'user_session'

# Создаем клиент и запускаем его
client = TelegramClient(session_name, api_id, api_hash)

async def main():
    # Запускаем клиент
    await client.start()

    # Проверяем, авторизованы ли мы
    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"Авторизация успешна! Пользователь: {me.first_name} (@{me.username})")

        # Получаем список диалогов
        dialogs = await client.get_dialogs()
        print("\nСписок каналов, где вы администратор:")
        for dialog in dialogs:
            try:
                if dialog.is_channel:
                    permissions = await client.get_permissions(dialog.entity)
                    if permissions.is_admin:
                        print(f"ID: {dialog.entity.id} | Название: {dialog.entity.title}")
            except Exception as e:
                pass
    else:
        print("Авторизация не удалась")

# Запускаем функцию
with client:
    client.loop.run_until_complete(main())
