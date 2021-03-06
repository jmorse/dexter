# DExTer : Debugging Experience Tester
# ~~~~~~   ~         ~~         ~   ~~
#
# Copyright (c) 2018 by SN Systems Ltd., Sony Interactive Entertainment Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
"""Interface for communicating with the LLDB debugger via its python interface.
"""

import imp
import os
from subprocess import CalledProcessError, check_output, STDOUT
import sys

from dex.debugger.DebuggerBase import DebuggerBase
from dex.dextIR import FrameIR, LocIR, StepIR, StopReason, ValueIR
from dex.utils.Exceptions import DebuggerException, LoadDebuggerException


class LLDB(DebuggerBase):
    def __init__(self, context, *args):
        self.lldb_executable = context.options.lldb_executable
        self._debugger = None
        self._target = None
        self._process = None
        self._thread = None
        super(LLDB, self).__init__(context, *args)

    def _custom_init(self):
        self._debugger = self._interface.SBDebugger.Create()
        self._debugger.SetAsync(False)
        self._target = self._debugger.CreateTargetWithFileAndArch(
            self.context.options.executable, self.context.options.arch)
        if not self._target:
            raise LoadDebuggerException(
                'could not create target for executable "{}" with arch:{}'.
                format(self.context.options.executable,
                       self.context.options.arch))

    def _custom_exit(self):
        if getattr(self, '_process', None):
            self._process.Kill()
        if getattr(self, '_debugger', None) and getattr(self, '_target', None):
            self._debugger.DeleteTarget(self._target)

    def _translate_stop_reason(self, reason):
        if reason == self._interface.eStopReasonNone:
            return None
        if reason == self._interface.eStopReasonBreakpoint:
            return StopReason.BREAKPOINT
        if reason == self._interface.eStopReasonPlanComplete:
            return StopReason.STEP
        if reason == self._interface.eStopReasonThreadExiting:
            return StopReason.PROGRAM_EXIT
        if reason == self._interface.eStopReasonException:
            return StopReason.ERROR
        return StopReason.OTHER

    def _load_interface(self):
        try:
            args = [self.lldb_executable, '-P']
            pythonpath = check_output(
                args, stderr=STDOUT).rstrip().decode('utf-8')
        except CalledProcessError as e:
            raise LoadDebuggerException(str(e), sys.exc_info())
        except OSError as e:
            raise LoadDebuggerException(
                '{} ["{}"]'.format(e.strerror, self.lldb_executable),
                sys.exc_info())

        if not os.path.isdir(pythonpath):
            raise LoadDebuggerException(
                'path "{}" does not exist [result of {}]'.format(
                    pythonpath, args), sys.exc_info())

        try:
            module_info = imp.find_module('lldb', [pythonpath])
            return imp.load_module('lldb', *module_info)
        except ImportError as e:
            msg = str(e)
            if msg.endswith('not a valid Win32 application.'):
                msg = '{} [Are you mixing 32-bit and 64-bit binaries?]'.format(
                    msg)
            raise LoadDebuggerException(msg, sys.exc_info())

    @classmethod
    def get_name(cls):
        return 'lldb'

    @classmethod
    def get_option_name(cls):
        return 'lldb'

    @property
    def version(self):
        try:
            return self._interface.SBDebugger_GetVersionString()
        except AttributeError:
            return None

    def clear_breakpoints(self):
        self._target.DeleteAllBreakpoints()

    def add_breakpoint(self, file_, line):
        if not self._target.BreakpointCreateByLocation(file_, line):
            raise LoadDebuggerException(
                'could not add breakpoint [{}:{}]'.format(file_, line))

    def launch(self):
        self._process = self._target.LaunchSimple(None, None, os.getcwd())
        if not self._process:
            raise DebuggerException('could not launch process')
        if self._process.GetNumThreads() != 1:
            raise DebuggerException('multiple threads not supported')
        self._thread = self._process.GetThreadAtIndex(0)
        assert self._thread, (self._process, self._thread)

    def step(self):
        self._thread.StepInto()

    def go(self):
        self._process.Continue()

    def get_step_info(self):
        frames = []

        for i in range(0, self._thread.GetNumFrames()):
            sb_frame = self._thread.GetFrameAtIndex(i)
            sb_line = sb_frame.GetLineEntry()
            sb_filespec = sb_line.GetFileSpec()

            try:
                path = os.path.join(sb_filespec.GetDirectory(),
                                    sb_filespec.GetFilename())
            except (AttributeError, TypeError):
                path = None

            function = self._sanitize_function_name(sb_frame.GetFunctionName())

            loc = LocIR(
                path=path,
                lineno=sb_line.GetLine(),
                column=sb_line.GetColumn())

            frame = FrameIR(
                function=function, is_inlined=sb_frame.IsInlined(), loc=loc)

            if any(
                    name in (frame.function or '')  # pylint: disable=no-member
                    for name in self.frames_below_main):
                break

            frames.append(frame)

        if len(frames) == 1 and frames[0].function is None:
            frames = []

        reason = self._translate_stop_reason(self._thread.GetStopReason())

        return StepIR(
            step_index=self.step_index, frames=frames, stop_reason=reason)

    @property
    def is_running(self):
        # We're not running in async mode so this is always False.
        return False

    @property
    def is_finished(self):
        return not self._thread.GetFrameAtIndex(0)

    @property
    def frames_below_main(self):
        return ['__scrt_common_main_seh', '__libc_start_main']

    def evaluate_expression(self, expression):
        result = self._thread.GetFrameAtIndex(0).EvaluateExpression(expression)
        error_string = str(result.error)

        value = result.value
        could_evaluate = not any(s in error_string for s in [
            "Can't run the expression locally",
            "use of undeclared identifier",
            "Couldn't lookup symbols",
        ])

        is_optimized_away = any(s in error_string for s in [
            'value may have been optimized out',
        ])

        is_irretrievable = any(s in error_string for s in [
            "couldn't get the value of variable",
            "couldn't read its memory",
            "couldn't read from memory",
        ])

        if could_evaluate and not is_irretrievable and not is_optimized_away:
            assert error_string == 'success', (error_string, expression, value)
            # assert result.value is not None, (result.value, expression)

        if error_string == 'success':
            error_string = None

        return ValueIR(
            expression=expression,
            value=value,
            type=str(result.type),
            error_string=error_string,
            could_evaluate=could_evaluate,
            is_optimized_away=is_optimized_away,
            is_irretrievable=is_irretrievable,
        )
