import inspect
import time
from typing import List

from pyrogram import Filters
from pyrogram.api.functions.messages import DeleteHistory
from pyrogram.api.functions.users import GetFullUser
from pyrogram.api.types import BotCommand
from .awaitableaction import AwaitableAction
from .interactionclient import InteractionClient
from .response import Response


class BotIntegrationClient(InteractionClient):
    def __init__(
            self,
            bot_under_test,
            session_name=None,
            api_id=None,
            api_hash=None,
            phone_number=None,
            max_wait_response=15,
            min_wait_consecutive=2,
            global_delay=0.2,
            raise_no_response=True,
            **kwargs):

        super().__init__(
            session_name=session_name,
            api_id=api_id,
            api_hash=api_hash,
            phone_number=phone_number,
            **kwargs
        )

        self.bot_under_test = bot_under_test
        self.max_wait_response = max_wait_response
        self.min_wait_consecutive = min_wait_consecutive
        self.raise_no_response = raise_no_response
        self.global_action_delay = global_delay

        self.peer = None
        self.peer_id = None
        self.command_list = None

        self._last_response = None

    def get_default_filters(self, user_filters=None):
        if user_filters is None:
            return Filters.chat(self.peer_id) & Filters.incoming
        else:
            return user_filters & Filters.chat(self.peer_id) & Filters.incoming

    def send(self, data):
        """Use this method to send Raw Function queries.

        Adapted to include the global delays.

        This method makes possible to manually call every single Telegram API method in a low-level manner.
        Available functions are listed in the :obj:`functions <pyrogram.api.functions>` package and may accept
        compound data types from :obj:`types <pyrogram.api.types>` as well as bare types such as ``int``, ``str``,
        etc...

        Args:
            data (``Object``):
                The API Scheme function filled with proper arguments.

        Raises:
            :class:`Error <pyrogram.Error>`
        """
        return super().send(data)

    def act_await_response(self, action: AwaitableAction, raise_=True) -> Response:
        if self.global_action_delay and self._last_response:
            # Sleep for as long as the global delay prescribes
            sleep = self.global_action_delay - (time.time() - self._last_response.started)
            if sleep > 0:
                time.sleep(sleep)

        response = super().act_await_response(action, raise_=raise_)
        self._last_response = response
        return response

    def start(self, debug=False):
        """Use this method to start the Client after creating it.
        Requires no parameters.

        Args:
            debug (``bool``, optional):
                Enable or disable debug mode. When enabled, extra logging
                lines will be printed out on your console.

        Raises:
            :class:`Error <pyrogram.Error>`
        """
        res = super().start(debug=debug)

        self.peer = self.resolve_peer(self.bot_under_test)
        self.peer_id = self.peer.user_id
        self.command_list = self._get_command_list()

        return res

    def ping(self, override_messages=None):
        """
        Send messages to a bot to determine whether it is online.

        Specify a list of ``override_messages`` that should be sent to the bot, defaults to /start.

        Args:
            override_messages: List of messages to be sent

        Returns:
            Response
        """

        # TODO: should this method also handle inline queries?

        return super().ping_bot(
            peer=self.peer_id,
            override_messages=override_messages,
            max_wait_response=self.max_wait_response,
            min_wait_consecutive=self.min_wait_consecutive
        )

    def _get_command_list(self) -> List[BotCommand]:
        return self.send(
            GetFullUser(
                id=self.peer
            )
        ).bot_info.commands

    def clear_chat(self):
        self.send(DeleteHistory(self.peer, max_id=0, just_clear=False))


def __modify_await_arg_defaults(class_, method_name, await_method):
    def f(self, *args, filters=None, num_expected=None, raise_=True, **kwargs):
        # Make sure arguments aren't passed twice
        default_args = dict(
            max_wait=self.max_wait_response,
            min_wait_consecutive=self.min_wait_consecutive,
            raise_=raise_ if raise_ is not None else self.raise_no_response
        )
        default_args.update(**kwargs)

        return await_method(
            self,
            self.peer_id,
            *args,
            filters=self.get_default_filters(filters),
            num_expected=num_expected,
            **default_args
        )

    f.__name__ = method_name
    setattr(class_, method_name, f)


for name, method in inspect.getmembers(BotIntegrationClient, inspect.isfunction):
    if name.endswith('_await'):
        __modify_await_arg_defaults(BotIntegrationClient, name, method)
