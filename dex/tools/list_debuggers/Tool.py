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
"""List debuggers tool."""

from dex.debugger.Debuggers import add_debugger_tool_arguments1
from dex.debugger.Debuggers import handle_debugger_tool_options1
from dex.debugger.Debuggers import Debuggers
from dex.tools import ToolBase
from dex.utils import Timer
from dex.utils.Exceptions import DebuggerException, Error


class Tool(ToolBase):
    """List all of the potential debuggers that DExTer knows about and whether
    there is currently a valid interface available for them.
    """

    @property
    def name(self):
        return 'DExTer list debuggers'

    def add_tool_arguments(self, parser, defaults):
        parser.description = Tool.__doc__
        add_debugger_tool_arguments1(parser, defaults)

    def handle_options(self, defaults):
        handle_debugger_tool_options1(self.context, defaults)

    def go(self):
        with Timer('list debuggers'):
            try:
                Debuggers(self.context).list()
            except DebuggerException as e:
                raise Error(e)
        return 0
