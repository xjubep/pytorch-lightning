import logging
import os
import signal
import sys
from typing import Any, Dict, List, Optional, Union

from lightning_app import LightningWork
from lightning_app.storage.payload import Payload
from lightning_app.utilities.app_helpers import _collect_child_process_pids
from lightning_app.utilities.tracer import Tracer

logger = logging.getLogger(__name__)


class TracerPythonScript(LightningWork):
    def on_before_run(self):
        """Called before the python script is executed."""

    def on_after_run(self, res: Any):
        """Called after the python script is executed."""
        for name in self.outputs:
            setattr(self, name, Payload(res[name]))

    def configure_tracer(self) -> Tracer:
        """Override this hook to customize your tracer when running PythonScript."""
        return Tracer()

    def __init__(
        self,
        script_path: str,
        script_args: Optional[Union[list, str]] = None,
        outputs: Optional[List[str]] = None,
        env: Optional[Dict] = None,
        **kwargs,
    ):
        """The TracerPythonScript class enables to easily run a python script.

        When subclassing this class, you can configure your own :class:`~lightning_app.utilities.tracer.Tracer`
        by :meth:`~lightning_app.components.python.tracer.TracerPythonScript.configure_tracer` method

        The tracer is quite a magical class. It enables you to inject core into a script execution without changing it.

        Arguments:
            script_path: Path of the python script to run.
            script_path: The arguments to be passed to the script.
            outputs: Collection of object names to collect after the script execution.
            env: Environment variables to be passed to the script.
            kwargs: LightningWork Keyword arguments.

        Raises:
            FileNotFoundError: If the provided `script_path` doesn't exists.

        **How does it works ?**

        It works by executing the python script with python built-in `runpy
        <https://docs.python.org/3/library/runpy.html>`_ run_path method.
        This method takes any python globals before executing the script,
        e.g you can modify classes or function from the script.

        .. doctest::

            >>> from lightning_app.components.python import TracerPythonScript
            >>> f = open("a.py", "w")
            >>> f.write("print('Hello World !')")
            22
            >>> f.close()
            >>> python_script = TracerPythonScript("a.py")
            >>> python_script.run()
            Hello World !
            >>> os.remove("a.py")

        In the example below, we subclass the  :class:`~lightning_app.components.python.TracerPythonScript`
        component and override its configure_tracer method.

        Using the Tracer, we are patching the ``__init__`` method of the PyTorch Lightning Trainer.
        Once the script starts running and if a Trainer is instantiated, the provided ``pre_fn`` is
        called and we inject a Lightning callback.

        This callback has a reference to the work and on every batch end, we are capturing the
        trainer ``global_step`` and ``best_model_path``.

        Even more interesting, this component works for ANY Pytorch Lightning script and
        its state can be used in real time in a UI.

        .. literalinclude:: ../../../../examples/app_components/python/component_tracer.py
            :language: python


        Once implemented, this component can easily be integrated within a larger app
        to execute a specific python script.

        .. literalinclude:: ../../../../examples/app_components/python/app.py
            :language: python
        """
        super().__init__(**kwargs)
        if not os.path.exists(script_path):
            raise FileNotFoundError(f"The provided `script_path` {script_path}` wasn't found.")
        self.script_path = str(script_path)
        if isinstance(script_args, str):
            script_args = script_args.split(" ")
        self.script_args = script_args if script_args else []
        self.env = env
        self.outputs = outputs or []
        for name in self.outputs:
            setattr(self, name, None)

    def run(self, **kwargs):
        kwargs = {k: v.value if isinstance(v, Payload) else v for k, v in kwargs.items()}
        init_globals = globals()
        init_globals.update(kwargs)
        self.on_before_run()
        env_copy = os.environ.copy()
        if self.env:
            os.environ.update(self.env)
        res = self._run_tracer(init_globals)
        os.environ = env_copy
        return self.on_after_run(res)

    def _run_tracer(self, init_globals):
        sys.argv = [self.script_path]
        tracer = self.configure_tracer()
        return tracer.trace(self.script_path, *self.script_args, init_globals=init_globals)

    def on_exit(self):
        for child_pid in _collect_child_process_pids(os.getpid()):
            os.kill(child_pid, signal.SIGTERM)


__all__ = ["TracerPythonScript"]
