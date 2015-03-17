"""cosmic-ray

Usage:
  cosmic-ray [options] <module> <test-dir>

Options:
  -h --help          Show this screen.
  --verbose          Produce verbose output
  --no-local-import  Allow importing module from the current directory
"""
from functools import partial
import json
import logging
import multiprocessing
import sys

import docopt

from cosmic_ray.find_modules import find_modules
from cosmic_ray.mutating import run_with_mutants
from cosmic_ray.operators import all_operators
from cosmic_ray.testing import run_tests

log = logging.getLogger()


def format_response(response):
    rec = response[0]

    return '{outcome} -> {desc} @ {filename}:{lineno}'.format(
        outcome=response[1],
        desc=rec['description'],
        filename=rec['filename'],
        lineno=rec['line_number'])


def full_module_test(top_module, test_dir):
    """Runs the tests in `test_dir` against mutated version of
    `top_module`.

    This finds all of the modules in and including `top_module`. For
    each of these modules, it mutates them using all of the available
    mutation operators. For each mutant, the tests in `test_dir` are
    executed. The result of a bunch of records telling us whether the
    mutant survived, was killed, or was incompetent.
    """
    modules = list(find_modules(top_module))

    # Remove those names from sys.modules. Tests will import them on
    # their own after mutation.
    # TODO: This doesn't seem necessary now.
    for m in modules:
        del sys.modules[m.__name__]

    test_runner = partial(run_tests, test_dir)

    mp_mgr = multiprocessing.Manager()
    response_queue = mp_mgr.Queue()

    for m in modules:
        for op in all_operators():
            p = multiprocessing.Process(
                target=run_with_mutants,
                args=(m.__file__,
                      m.__name__,
                      op,
                      test_runner,
                      response_queue))
            p.start()
            p.join()

    # TODO: This is what we want to do, but apparently test discovery is not
    # reloading modules as we expect. Sort this out.
    #
    # with multiprocessing.Pool() as p:
    #     p.starmap(
    #         run_with_mutants,
    #         [(m.__file__, m.__name__, op, test_runner, response_queue)
    #          for m in modules
    #          for op in all_operators()])

    while not response_queue.empty():
        print(format_response(response_queue.get()))


def main():
    arguments = docopt.docopt(__doc__, version='cosmic-ray v.1')
    if arguments['--verbose']:
        logging.basicConfig(level=logging.INFO)

    if not arguments['--no-local-import']:
        sys.path.insert(0, '')

    full_module_test(
        arguments['<module>'],
        arguments['<test-dir>'])

if __name__ == '__main__':
    main()
