import asyncio
import datetime
from typing import Optional

from telethon import TelegramClient, events
from telethon.errors import UserAdminInvalidError, FloodWaitError
from telethon.events import NewMessage
from telethon.tl.custom import Message
from telethon.tl.functions.channels import GetParticipantRequest, EditBannedRequest
from telethon.tl.types import User, Channel, ChannelParticipantAdmin, ChatBannedRights
import config

import logging

from utilities.mdtex import MDTeXDocument, Bold, Section, KeyValueItem, SubSection, Mention

logging.basicConfig(level=logging.WARNING)

bot = TelegramClient('inactivity_checker', 653921, config.api_hash)


@bot.on(events.NewMessage(incoming=True, pattern='info'))
async def pn_info(event: NewMessage.Event) -> None:
    client: TelegramClient = event.client
    msg: Message = event.message
    user: User = await msg.get_sender()
    if not event.is_private:
        return

    await msg.reply(f' Hallo {user.first_name} Ich bin ein vollautomatisierter Account betrieben von @GodOfOwls.\n\n'

                    f'Ich kann dir Helfen deine Gruppe frei von Inaktiven Leuten zu halten.\n'
                    f'Um einen Check auszuführen fügst du mich der Gruppe hinzu und schreibst dann dort  `..inaktivität`'
                    f'\n\n'
                    f'Daraufhin werde ich die Gruppe nach Leuten durchsuchen die keine Nachricht darin haben (dazu '
                    f'zählen auch Leute deren Nachrichten wieder gelöscht wurden'
                    f'\n'
                    f'\n'
                    f'Wenn ich Bannrechte habe werde ich die User auch sofort aus der Gruppe entfernen.'
                    f'\n'
                    f'\n'
                    f'Es ist egal seit wann ich in der Gruppe bin. Also wenn du nicht möchtest das ich permanent in '
                    f'der Gruppe bin darfst du mich auch gerne wieder entfernen und wieder hinzufügen wenn du den '
                    f'nächsten check machen möchtest.', parse_mode='markdown')


@bot.on(events.NewMessage(outgoing=True, pattern='..inaktivität'))
async def cleanup(event: NewMessage.Event) -> None:
    """Command to remove Deleted Accounts from a group or network."""
    chat: Channel = await event.get_chat()
    client: TelegramClient = event.client

    if not chat.creator and not chat.admin_rights:
        count_only = True

    else:
        count_only = False

    waiting_message = await client.send_message(event.chat, 'Starting cleanup. This might take a while.')
    response = await _cleanup_chat(event, count=count_only, progress_message=waiting_message)

    if waiting_message:
        await waiting_message.delete()
    if response:
        await client.send_message(event.chat, response)


@bot.on(events.NewMessage(incoming=True, pattern='..inaktivität'))
async def cleanup_group_admins(event: NewMessage.Event) -> None:
    """Check if the issuer of the command is group admin. Then execute the cleanup command."""
    chat: Channel = await event.get_chat()

    if event.is_channel:
        msg: Message = event.message
        client: TelegramClient = event.client
        uid = msg.from_id
        result = await client(GetParticipantRequest(event.chat_id, uid))
        if isinstance(result.participant, ChannelParticipantAdmin):
            await cleanup(event)


async def _cleanup_chat(event, count: bool = False,
                        progress_message: Optional[Message] = None) -> str:
    chat: Channel = await event.get_chat()
    client: TelegramClient = event.client
    user: User
    deleted_users = 0
    deleted_admins = 0
    user_counter = 0
    deleted_accounts_label = Bold('Counted Inactive Accounts')
    participant_count = (await client.get_participants(chat, limit=0)).total
    # the number will be 0 if the group has less than 25 participants
    modulus = (participant_count // 25) or 1
    inactive_users = ''
    async for user in client.iter_participants(chat):
        if progress_message is not None and user_counter % modulus == 0:
            progress = Section(Bold('Cleanup'),
                               KeyValueItem(Bold('Progress'),
                                            f'{user_counter}/{participant_count}'),
                               KeyValueItem(deleted_accounts_label, deleted_users))
            await progress_message.edit(str(progress))
        user_counter += 1

        resultat = await client.get_messages(chat, from_user=user)
        if resultat.total == 0:
            deleted_users += 1

            if not count:
                try:
                    await client(EditBannedRequest(chat, user, ChatBannedRights(until_date=datetime.datetime(2038, 1, 1),
                                                                            view_messages=True)))
                except UserAdminInvalidError:
                    deleted_admins += 1
                except FloodWaitError as error:
                    if progress_message is not None:
                        progress = Section(Bold('Cleanup | FloodWait'),
                                       Bold(f'Got FloodWait for {error.seconds}s. Sleeping.'),
                                       KeyValueItem(Bold('Progress'),
                                                    f'{user_counter}/{participant_count}'),
                                       KeyValueItem(deleted_accounts_label, deleted_users))
                        await progress_message.edit(str(progress))

                    await asyncio.sleep(error.seconds)
                    await client(EditBannedRequest(chat, user, ChatBannedRights(until_date=datetime.datetime(2038, 1, 1),
                                                                            view_messages=True)))
            elif count:
                inactive_users += f'\n {Mention(user.first_name, user.id)}'


    return str((
        Section(Bold('Cleanup'),
                KeyValueItem(deleted_accounts_label, deleted_users),
                KeyValueItem(Bold('Inactive Admins'), deleted_admins) if deleted_admins else None,
        SubSection(Bold('Users:'),
                    inactive_users

                   ) if len(inactive_users) >= 2 else None

                )))


def main():
    """Start the bot."""
    bot.start()
    bot.run_until_disconnected()


if __name__ == '__main__':
    main()
