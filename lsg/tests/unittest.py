#!/usr/bin/env python3

import subprocess
import tempfile
import os
import sys
import shutil
import logging
import re
import yaml
import logging
import random
import signal
logging.addLevelName( logging.WARNING, "\033[1;33m%s\033[1;0m" % logging.getLevelName(logging.WARNING))
logging.addLevelName( logging.ERROR, "\033[1;41m%s\033[1;0m" % logging.getLevelName(logging.ERROR))
logging.addLevelName( logging.INFO, "\033[1;34m%s\033[1;0m" % logging.getLevelName(logging.INFO))

SCRIPT_ROOT = os.path.dirname(__file__)
GDB_SCRIPT_TRACE = os.path.join(SCRIPT_ROOT, "gdb_trace.py")

class Testcase:
    def __init__(self, testcase):
        self.testcase = testcase
        self.variables = {'Compilation': Compilation}
        Compilation.globals = self.variables
        self.failed = False
        self.skipped_tests = 0

        with open(testcase) as fd:
            content = fd.read()
            self.load(content, execute=True)

    def load(self, content, execute=False):
        block_types = {
            '!yaml': self.block_yaml,
            '!source': self.block_source,
            '!python': self.block_nop,
            '!inherit': self.block_inherit,
        }
        if execute:
            block_types['!python'] = self.block_python

        blocks = re.split("\n---", "\n"+content)
        blocks = [x.lstrip() for x in blocks if x]
        # For every block, we call the block_ function with the given arguments
        for block in blocks:
            lines = (block + "\n").split("\n",1)
            block_args = lines[0].split()
            if block_args[0] not in block_types:
                sys.exit("Block type %s is unknown" % block_args[0])

            block_ret = block_types[block_args[0]](lines[1],*block_args[1:])
            if block_ret is False:
                self.failed = True
                return
            if block_ret is 'skipped':
                self.skipped_tests += 1


    def block_nop(self, *args, **kwargs):
        pass

    def block_yaml(self, block):
        self.variables.update(yaml.safe_load(block))
        return True

    def block_source(self, block, variable):
        self.variables[variable.strip()] = block
        return True

    def block_inherit(self, block, other_testcase):
        basedir = os.path.dirname(self.testcase)
        with open(os.path.join(basedir, other_testcase)) as fd:
            content = fd.read()
            self.load(content, execute=False)
        return True


    def block_python(self, block, *args):
        if args:
            logging.info("... Subtest: %s", " ".join(args))
        try:
            exec(block, self.variables)
            return True
        except TypeError as e:
            raise e
        except RuntimeError as e:
            logging.error("testcase failed: %s, %s", self.testcase, e)
            return False
        except RuntimeWarning as e:
            logging.warning(e)
            return 'skipped'
        except subprocess.TimeoutExpired as e:
            logging.error("testcase failed by timeout: %s, %s", self.testcase, e)
            out = e.stdout or ""
            err = e.stderr or ""
            logging.error("STDOUT:\n%s\nSTDERR:\n%s", out, red(err))
            return False




def red(msg):
    return "\x1b[31;4m%s\x1b[0m" % msg


class Compilation:
    """Compilation is executed in the context of a testcase"""

    globals = None

    instances = []

    no_strace = False

    def __init__(self, after_main = None, before_main=None, source_files=None):
        if source_files is None:
            if 'sources' in Compilation.globals:
                source_files = Compilation.globals['sources']
            else:
                sys.exit("Invalid Testcase: No sources given")
        assert type(source_files) is dict, "source_files must be a dict"
        self.source_files = source_files
        for fn in source_files:
            assert os.path.exists(fn) or 'content' in source_files[fn], "File %s does not exist" % fn

        self.after_main = after_main
        self.before_main = before_main
        self.tmpdir = tempfile.mkdtemp(prefix="gbs_test_")
        # We use a random number as a flag to replace {{{FINISHED}}}
        # in the output.
        self.flag = str(random.randint(0, 10000000))
        Compilation.instances.append(self)

    def fail_marker(self, marker, msg):
        if not self.after_main:
            raise RuntimeError(msg)
        lines = self.after_main.split("\n")
        for idx, line in enumerate(lines):
            if "Marker " + str(marker) in line:
                lines[idx] = "// --> " + red("Error is around here")
            elif "Marker" in line:
                lines[idx] = None
        logging.error(red(msg) + "\n" + "\n".join([x for x in lines if x is not None]))

        raise RuntimeError(msg)

    def compile(self, flags=[], remap=None):
        try:
            # There are default flags
            flags += Compilation.globals.get('cflags', [])
            return self.__compile(flags, remap)
        except subprocess.CalledProcessError as e:
            logging.error("Compilation failed: %s", e.args)
            raise RuntimeError("Compilation Failed")

    def __compile(self, flags=[], remap=None):
        if remap is None:
            remap = {}

        if self.after_main:
            remap['main'] = 'studentMain'


        found_main = False
        for fn in self.source_files:
            src, dst = fn, os.path.join(self.tmpdir, os.path.basename(fn))

            if 'content' in self.source_files[fn]:
                content = self.source_files[fn]['content']
            else:
                with open(src) as fd:
                    content = fd.read()

            if self.source_files[src].get('main'):
                found_main = True
                before = ""
                after = ""
                for oldname, newname in remap.items():
                    before += "#define %s %s\n" % (oldname, newname)
                    after  += "#undef %s\n" %(oldname)

                if self.before_main:
                    before = self.before_main + before

                if self.after_main:
                    after += self.after_main

                content = \
                     '#line 1 "<<before_main>>"\n'  \
                    + before \
                    + '#line 1 "%s"\n' % src \
                    + content \
                    + '\n#line 1 "<<after_main>>"\n'  \
                    + after.replace("{{{FINISHED}}}", self.flag)

            with open(dst, "w+") as fd:
                fd.write(content)

        assert found_main, "One source file must be attributed with 'main: true'"

        object_files = []
        logging.debug("Compile sources: %s", self.source_files)
        for fn in self.source_files:
            if not fn.endswith(".c"):
                continue
            obj = os.path.join(self.tmpdir, os.path.basename(fn) + ".o")
            subprocess.check_output(["gcc"] + flags + ["-c", "-o", obj,
                                                       os.path.join(self.tmpdir, fn)])
            object_files += [obj]
        main = os.path.join(self.tmpdir, 'main')

        logging.debug("Link objects: %s", object_files)

        subprocess.check_output(["gcc"] + flags + object_files + ["-o", main])
        self.main = main

        return self

    def run(self, args = [], cmd_prefix = [],
            must_fail=False,
            retcode_expected = lambda retcode: retcode != 0,
            input=None, **kwargs):
        input = input.encode() if type(input) == str else input
        input_ = input.replace(b"{{{FINISHED}}}", self.flag.encode()) if type(input) == bytes else None
        (retcode, cmd, stdout, stderr) = self.__run(args, cmd_prefix, input=input_, **kwargs)
        stdout = stdout.decode(errors='replace')
        stderr = stderr.decode(errors='replace')
        if retcode < 0:
            stderr += "<<Killed by Signal '%s'>>" % (signal.Signals(retcode * -1))

        if self.after_main:
            m = re.search("<<after_main>>:([0-9]*)", stderr)
            after_main_txt = self.after_main
            if m:
                line = int(m.group(1))
                lines = self.after_main.split("\n")
                if line < len(lines):
                    lines[line-2] += "  // " + red("<- ERROR")
                    after_main_txt = "\n".join(lines)

        logging.debug("Run: %s, [retcode=%d]",
                      cmd_prefix+args, retcode)
        if retcode != 0 and not must_fail:
            msg = "Program Run failed (exitcode={}) unexpected: {} ".format(retcode, cmd)
            logging.error("%s\nSTDOUT:\n%s\nSTDERR:\n%s", red(msg),
                          stdout, red(stderr))
            if input_:
                logging.error("STDIN:\n%s\n", input_.decode())
            if self.after_main:
                logging.info("\n%s", after_main_txt)
            raise RuntimeError(msg)
        elif must_fail and not retcode_expected(retcode):
            msg = "Program Run did not fail while it should: " + str((retcode, cmd))
            logging.error("%s\nSTDOUT:\n%s\nSTDERR:\n%s", red(msg),
                          stdout, red(stderr))
            if input_:
                logging.error("STDIN:\n%s\n", input_.decode())
            if self.after_main:
                logging.info("\n%s", after_main_txt)
            raise RuntimeError(msg)
        else:
            # If the testcase was successful, we look for our flag in
            # the stdout output. If this was not present, the user
            # probably cheated on us.
            if (self.after_main and "{{{FINISHED}}}" in self.after_main) or\
               (input and b"{{{FINISHED}}}" in input):
                if self.flag not in stdout:
                    msg="Testcase was not run until the end. Flag was not found."
                    logging.error("%s\nSTDOUT:\n%s\nSTDERR:\n%s", red(msg),
                          stdout, red(stderr))
                    if input_:
                        logging.error("STDIN:\n%s\n", input_.decode())
                    raise RuntimeError("Testcase was not run until the end")

        return stdout, stderr

    def __run(self, args = [], cmd_prefix = [], input=None, **kwargs):
        assert self.main, "Compilation failed"
        cmd = cmd_prefix + [self.main] + args
        stdin = subprocess.PIPE if input else subprocess.DEVNULL
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             stdin=stdin, **kwargs)
        stdout, stderr = p.communicate(input=input, timeout=10)
        return (p.returncode, cmd, stdout, stderr)

    def trace(self, functions, **kwargs):
        log_file = tempfile.NamedTemporaryFile()
        logging.debug(log_file.name)
        os.environ['TRACE_FILE'] = log_file.name
        os.environ['TRACE_FUNCTIONS'] = ','.join(functions)
        if not os.path.exists(GDB_SCRIPT_TRACE):
            m = "GDB_SCRIPT_TRACE not found: " + GDB_SCRIPT_TRACE
            raise RuntimeError(m)
        cmd_prefix = ["gdb", '-nx', "-x", GDB_SCRIPT_TRACE]
        output = self.run(cmd_prefix=cmd_prefix, **kwargs)
        ret = []
        for line in log_file.readlines():
            print(line)
            ret.append(eval(line))

        return Trace(ret)

    def strace(self, syscalls=None, **kwargs):
        if Compilation.no_strace:
            raise RuntimeWarning("strace is not installed. Test skipped.")
        log_file = tempfile.NamedTemporaryFile()
        try:
            cmd_prefix = ["strace", '-qqf', '-o', log_file.name]
            if syscalls:
                cmd_prefix += ['-e','trace='+syscalls]
            (stdout, stderr) = self.run(cmd_prefix=cmd_prefix, **kwargs)
            lines = log_file.readlines()
            lines = [l.decode() for l in lines]
            return stdout, stderr, lines
        except FileNotFoundError as e:
            if e.filename == cmd_prefix[0]:
                Compilation.no_strace = True
                raise RuntimeWarning("strace is not installed. "\
                                   "To run this test install strace."\
                                   "\n  apt-get install strace\n")
            raise RuntimeError(dir(e))

    def cleanup(self):
        if self.tmpdir is None:
            return
        shutil.rmtree(self.tmpdir)
        self.tmpdir = None

class Trace:
    def __init__(self, records):
        invocations = {}
        for x in records:
            if x[0] == "call":
                _, parent, child, name, asm_name, args = x
                invocations[child] = {
                    'id': child,
                    'name': name,
                    'asm_name': asm_name,
                    'args': args,
                    'parent': None,
                    'return': None,
                    'children': []
                }
                if parent is not None:
                    invocations[child]['parent'] = invocations[parent]
                    invocations[parent]['children'].append(invocations[x[1]])
            elif x[0] == "return":
                _, id, _, ret = x
                invocations[id]['return'] = ret

        self.records = invocations


    def function_called(self, name):
        for record in sorted(self.records.values(), key=lambda x: x['id']):
            if type(name) is str and record['name'] == name:
                yield record
            if type(name) in [list, tuple] and record['name'] in name:
                yield record


if __name__ == "__main__":
    import argparse
    import glob
    parser = argparse.ArgumentParser(description='GBS Testcase Tool.')
    parser.add_argument('-t', '--testcases', dest='testcases',
                        default = "tests",
                        help='Testcase(s) - directory or file')
    parser.add_argument('-v', '--verbose', dest='verbose',
                        action="store_true",
                        default = False,
                        help='verbose output')

    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    if os.path.isdir(args.testcases):
        testcases = glob.glob(os.path.join(args.testcases, "*.test"))
    else:
        testcases = [args.testcases]

    results = []
    for test in sorted(testcases):
        # Execute testcase
        logging.info("Testcase: %s", test)
        t = Testcase(test)
        results.append(t)

    for c in Compilation.instances:
        c.cleanup()
        pass

    if any([x.failed for x in results ]):
        print()
        sys.exit("Failed Testcases: \n - " + "\n - ".join([x.testcase for x in results if x.failed]))
    if any([x.skipped_tests for x in results]):
        sys.exit("{} test(s) were skipped."\
                 .format(sum([x.skipped_tests for x in results])))
