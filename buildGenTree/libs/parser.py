import argparse
import logging
import os


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description = 'This is a first version to build a Genome Tree'
    )

    # Required group.
    cmd = parser.add_argument_group('Commands')
    cmd.add_argument(
        'st',
        help = 'Sequence type to be filter.',
        type = int,
    )
    cmd.add_argument(
        dest="file_src",
        default=None,
        help="Set tsv source file path",
    )
    cmd.add_argument(
        'group',
        help = 'Organism group to be filter.',
        nargs = '+',
    )

    # Options group.
    opts = parser.add_argument_group('Common options')
    opts.add_argument(
        '--tsv-out-file',
        help = 'Name of the output tsv file.',
        type = str,
        dest = 'out_file',
    )
    opts.add_argument(
        "-s",
        "--stream-output",
        dest="stream_output",
        help="Stream output to stdout",
        action="store_true",
    )
    opts.add_argument(
        '-i', '--install',
        help = 'Task to be performed.',
        action="store_true",
        dest='install',
    )
    opts.add_argument(
        '--log-level',
        dest='log_level',
        default=logging.INFO,
        type=lambda x: getattr(logging, x),
        help='Configure the logging level.',
    )
    parser.add_argument(
        '-v', '--version',
        action = 'version',
        version = 'buildGenTree v1.0.0',
    )
    return parser
