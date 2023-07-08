#!/usr/bin/python
import base64
import io
import os
import subprocess
import sys
import time
from pathlib import Path


class System(object):
    @staticmethod
    def exec(args: str) -> dict:
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        process = subprocess.Popen(args,
                                   encoding='utf-8',
                                   stdout=subprocess.PIPE,
                                   shell=True,
                                   universal_newlines=True)

        output = []
        print_end('Starting book downloading:', ' ')
        # print('Starting book downloading:', end=' ')
        while True:
            out = process.stdout.readline().strip()
            if out != '':
                print_end('.', '')
                # print('.', end=' ')
                output.append(out)
            # Do something else
            return_code = process.poll()
            if return_code is not None:
                # Process has finished, read rest of the output
                # for output in process.stdout.readlines():
                #     print(output.strip())
                break
        if return_code == 0:
            print_end(' DONE.')
            # print('DONE.')
        else:
            print_end(f' ERROR (CODE={return_code})!!!')
        return {'output': output, 'return_code': return_code}


def unixtime() -> str:
    return str(round(time.time() * 1000))


def print_end(line: str, end='\n') -> None:
    sys.stdout.write(f"{line}{end}")
    sys.stdout.flush()


def file_get_contents(filename: str, encoding='utf-8') -> str | bool:
    if Path(filename).is_file():
        return Path(filename).read_text(encoding)
    else:
        return False


def file_put_contents(filename: str, data='', encoding='utf-8') -> int:
    return Path(filename).write_text(data, encoding)


def file_get_contents_base64(filename: str) -> str:
    # with open(filename, "rb") as file:
    with io.open(filename, "rb", buffering=0) as file:
        return str(base64.b64encode(file.read()))
