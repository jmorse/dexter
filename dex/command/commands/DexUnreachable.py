from dex.command.CommandBase import CommandBase
from dex.dextIR import ValueIR

class DexUnreachable(CommandBase):
  def __init(self):
    super(DexUnreachable, self).__init__()
    pass

  def __call__(self, debugger, step_info):
    # If we're ever called, at all, then we're evaluating a line that has
    # been marked as unreachable. Which means a failure.
    step_info.unreachable = True
    return dict()
