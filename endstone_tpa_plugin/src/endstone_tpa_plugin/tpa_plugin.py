from __future__ import annotations

from typing import Dict, Tuple

from endstone.command import Command, CommandSender
from endstone.event import PlayerQuitEvent, event_handler
from endstone.plugin import Plugin


class TpaPlugin(Plugin):
    """Simple teleport request plugin."""

    api_version = "0.5"

    commands = {
        "tpa": {
            "description": "Request to teleport to another player.",
            "usages": ["/tpa <player: string>"],
            "permissions": ["tpa.command.tpa"],
        },
        "tpaccept": {
            "description": "Accept a teleport request.",
            "usages": ["/tpaccept"],
            "permissions": ["tpa.command.tpaccept"],
        },
        "tpdeny": {
            "description": "Deny a teleport request.",
            "usages": ["/tpdeny"],
            "permissions": ["tpa.command.tpdeny"],
        },
    }

    permissions = {
        "tpa.command.tpa": {"default": True},
        "tpa.command.tpaccept": {"default": True},
        "tpa.command.tpdeny": {"default": True},
    }

    def on_enable(self) -> None:
        self._requests: Dict[str, Tuple[CommandSender, object]] = {}
        self.logger.info("TPA plugin enabled")

    def on_disable(self) -> None:
        for sender, task in self._requests.values():
            task.cancel()
        self._requests.clear()

    def on_command(self, sender: CommandSender, command: Command, args: list[str]) -> bool:
        name = command.name
        if name == "tpa":
            return self._handle_tpa(sender, args)
        if name == "tpaccept":
            return self._handle_tpaccept(sender)
        if name == "tpdeny":
            return self._handle_tpdeny(sender)
        return False

    def _handle_tpa(self, sender: CommandSender, args: list[str]) -> bool:
        if len(args) != 1:
            sender.send_message("Usage: /tpa <player>")
            return True

        target = self.server.get_player(args[0])
        if target is None:
            sender.send_message("Player not found.")
            return True

        if target.name == sender.name:
            sender.send_message("You cannot send a request to yourself.")
            return True

        if target.name in self._requests:
            requester, _ = self._requests[target.name]
            if requester == sender:
                sender.send_message("You already have a pending request to this player.")
            else:
                sender.send_message("This player already has a pending request.")
            return True

        sender.send_message(f"Teleport request sent to {target.name}.")
        target.send_message(
            f"{sender.name} has requested to teleport to you. Use /tpaccept to accept or /tpdeny to deny."
        )

        def expire() -> None:
            if self._requests.get(target.name, (None, None))[0] == sender:
                del self._requests[target.name]
                sender.send_message("Your teleport request has expired.")
                target.send_message("Teleport request expired.")

        task = self.server.scheduler.run_task(self, expire, delay=20 * 60)
        self._requests[target.name] = (sender, task)
        return True

    def _handle_tpaccept(self, sender: CommandSender) -> bool:
        if sender.name not in self._requests:
            sender.send_message("You have no pending request.")
            return True

        requester, task = self._requests.pop(sender.name)
        task.cancel()
        requester.send_message(f"{sender.name} accepted your teleport request.")
        sender.send_message(f"You accepted {requester.name}'s teleport request.")
        requester.teleport(sender)
        return True

    def _handle_tpdeny(self, sender: CommandSender) -> bool:
        if sender.name not in self._requests:
            sender.send_message("You have no pending request.")
            return True

        requester, task = self._requests.pop(sender.name)
        task.cancel()
        requester.send_message(f"{sender.name} denied your teleport request.")
        sender.send_message(f"You denied {requester.name}'s teleport request.")
        return True

    @event_handler
    def on_player_quit(self, event: PlayerQuitEvent) -> None:
        player_name = event.player.name
        if player_name in self._requests:
            requester, task = self._requests.pop(player_name)
            task.cancel()
            requester.send_message(f"{player_name} left the game. Teleport request cancelled.")
        to_cancel = [n for n, (req, _) in self._requests.items() if req.name == player_name]
        for target_name in to_cancel:
            requester, task = self._requests.pop(target_name)
            task.cancel()
            player = self.server.get_player(target_name)
            if player:
                player.send_message(f"{player_name} left the game. Teleport request cancelled.")