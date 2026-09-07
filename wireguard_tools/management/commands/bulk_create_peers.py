import csv

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from wireguard.models import PeerAllowedIP, WireGuardInstance
from wireguard_peer.functions import func_create_new_peer
from wireguard_tools.views import export_wireguard_configuration


class Command(BaseCommand):
    help = "Create WireGuard peers in bulk for one WireGuard instance."

    def add_arguments(self, parser):
        instance_group = parser.add_mutually_exclusive_group(required=True)
        instance_group.add_argument(
            "--instance-id",
            type=int,
            help="WireGuard instance id, for example 0 for wg0.",
        )
        instance_group.add_argument(
            "--instance-uuid",
            help="WireGuard instance UUID.",
        )
        parser.add_argument(
            "--count",
            type=int,
            default=70,
            help="Number of peers to create. Default: 70.",
        )
        parser.add_argument(
            "--name-prefix",
            default="peer",
            help="Peer name prefix. Names are generated as PREFIX001, PREFIX002, ...",
        )
        parser.add_argument(
            "--start",
            type=int,
            default=1,
            help="Starting number for generated peer names. Default: 1.",
        )
        parser.add_argument(
            "--export",
            action="store_true",
            help="Export WireGuard configuration after creating peers.",
        )
        parser.add_argument(
            "--csv",
            dest="csv_path",
            help="Write created peer details to a CSV file.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate options and show planned names without creating peers.",
        )

    def handle(self, *args, **options):
        count = options["count"]
        start = options["start"]
        if count < 1:
            raise CommandError("--count must be 1 or greater.")
        if start < 0:
            raise CommandError("--start must be 0 or greater.")

        instance = self._get_instance(options)
        names = [f"{options['name_prefix']}{number:03d}" for number in range(start, start + count)]

        if options["dry_run"]:
            self.stdout.write(f"Instance: wg{instance.instance_id} ({instance.uuid})")
            self.stdout.write(f"Peers to create: {count}")
            for name in names:
                self.stdout.write(f"  {name}")
            return

        created_rows = []
        with transaction.atomic():
            for name in names:
                peer, message = func_create_new_peer(instance, overrides={"name": name})
                if not peer:
                    raise CommandError(f"Failed to create {name}: {message}")

                server_ips = PeerAllowedIP.objects.filter(peer=peer, config_file="server").order_by("priority")
                client_routes = PeerAllowedIP.objects.filter(peer=peer, config_file="client").order_by("priority")
                created_rows.append({
                    "name": peer.name,
                    "uuid": str(peer.uuid),
                    "public_key": peer.public_key,
                    "server_allowed_ips": ", ".join(f"{ip.allowed_ip}/{ip.netmask}" for ip in server_ips),
                    "client_allowed_ips": ", ".join(f"{ip.allowed_ip}/{ip.netmask}" for ip in client_routes),
                })

        if options["csv_path"]:
            with open(options["csv_path"], "w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=created_rows[0].keys())
                writer.writeheader()
                writer.writerows(created_rows)

        if options["export"]:
            export_wireguard_configuration(instance)
            instance.pending_changes = False
        else:
            instance.pending_changes = True
        instance.save(update_fields=["pending_changes"])

        self.stdout.write(self.style.SUCCESS(f"Created {len(created_rows)} peers on wg{instance.instance_id}."))
        if options["csv_path"]:
            self.stdout.write(f"CSV written to {options['csv_path']}")
        if options["export"]:
            self.stdout.write("WireGuard configuration exported. Reload or restart the interface to apply changes.")
        else:
            self.stdout.write("Pending changes marked. Export/reload from the UI or rerun with --export.")

    def _get_instance(self, options):
        if options["instance_uuid"]:
            try:
                return WireGuardInstance.objects.get(uuid=options["instance_uuid"])
            except WireGuardInstance.DoesNotExist:
                raise CommandError(f"WireGuard instance with UUID {options['instance_uuid']} was not found.")

        try:
            return WireGuardInstance.objects.get(instance_id=options["instance_id"])
        except WireGuardInstance.DoesNotExist:
            raise CommandError(f"WireGuard instance wg{options['instance_id']} was not found.")
