import os

import click
import docker

from hydroserving.constants import PACKAGE_PATH
from hydroserving.context_object import ContextObject
from hydroserving.help import *
from hydroserving.helpers.docker import is_container_exists
from hydroserving.helpers import assemble_model, pack_model, read_contract, upload_model
from hydroserving.models import Metadata
from hydroserving.settings import CONTEXT_SETTINGS, Defaults


@click.group()
@click.pass_context
def hs_cli(ctx):
    ctx.obj = ContextObject()
    metadata = Metadata.from_directory(os.getcwd())
    ctx.obj.metadata = metadata


@hs_cli.command(help=STATUS_HELP)
@click.pass_obj
def status(obj):
    metadata = obj.metadata
    if metadata is None:
        click.echo("Directory doesn't have a serving metadata")
    else:
        click.echo("Detected a model: {}".format(metadata.model.name))
        click.echo("Model type: {}".format(metadata.model.model_type))
        click.echo("Files to upload:\n{}".format(metadata.model.payload))


@hs_cli.command()
@click.pass_obj
def pack(obj):
    metadata = ensure_metadata(obj)
    payload = pack_model(metadata.model)
    click.echo("Done. Packed: {}".format(payload))


@hs_cli.command()
@click.pass_obj
def assemble(obj):
    metadata = ensure_metadata(obj)
    assemble_model(metadata.model)
    click.echo("Done")


@hs_cli.command()
@click.pass_obj
def contract(obj):
    metadata = ensure_metadata(obj)
    click.echo("Reading contract...")
    contract_obj = read_contract(metadata.model)
    click.echo(contract_obj)


@hs_cli.command(help=UPLOAD_HELP, context_settings=CONTEXT_SETTINGS)
@click.option('--host',
              default=Defaults.HOST,
              show_default=True,
              help=UPLOAD_HOST_HELP,
              required=False)
@click.option('--port',
              default=Defaults.PORT,
              show_default=True,
              help=UPLOAD_PORT_HELP,
              required=False)
@click.pass_obj
def upload(obj, host, port):
    metadata = ensure_metadata(obj)
    upload_model(host, port, metadata.model)


# LOCAL DEPLOYMENT COMMANDS

@hs_cli.group(help=LOCAL_HELP)
@click.pass_context
def local(ctx):
    ctx.obj.docker_client = docker.from_env()


@local.command(help=START_HELP)
@click.pass_obj
def start(obj):
    metadata = obj.metadata
    if not os.path.exists(PACKAGE_PATH):
        click.echo("'{}' is not packed. Execute `pack` first.".format(metadata.model.name))
        raise SystemExit(-1)
    docker_client = obj.docker_client
    deployment_config = metadata.local_deployment
    if is_container_exists(docker_client, deployment_config.name):
        click.echo("'{}' container is already started.".format(deployment_config.name))
        raise SystemExit(-1)
    image = deployment_config.runtime
    docker_client.containers.run(
        str(image),
        remove=True, detach=True,
        name=metadata.local_deployment.name,
        ports={'9090/tcp': metadata.local_deployment.port},
        volumes={os.path.abspath(PACKAGE_PATH): {'bind': '/model', 'mode': 'ro'}}
    )
    click.echo("'{}' container is started.".format(deployment_config.name))


@local.command(help=STOP_HELP)
@click.pass_obj
def stop(obj):
    metadata = obj.metadata
    docker_client = obj.docker_client

    deployment_config = metadata.local_deployment
    if not is_container_exists(docker_client, deployment_config.name):
        click.echo("'{}' container is not found.".format(deployment_config.name))
        raise SystemExit(-1)
    container = docker_client.containers.get(deployment_config.name)
    container.remove(force=True)
    click.echo("'{}' container is removed".format(deployment_config.name))


def ensure_metadata(obj):
    if obj.metadata is None:
        click.echo("Directory doesn't have a serving metadata")
        raise SystemExit(-1)
    return obj.metadata
