from __future__ import absolute_import

from torch._six import string_classes

import laia.plugins.logging as log

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None


class Engine(object):
    r"""Wrapper class to train a model.

    Arguments:
      model: model to train.
      data_loader (iterable): iterable object from which batches are read.
      batch_input_fn (callable, optional): function used to extract the input
          for the model (e.g. a ``torch.Tensor``), from the batch loaded by
          the ``data_loader``. If ``None``, the batch is fed as-is to the
          model. (default: None)
      batch_target_fn (callable, optional): if given, this callable object
          is used to extract the targets from the batch, which are
          passed to the `ON_BATCH_START` and `ON_BATCH_END` hooks.
      progress_bar (bool or str, optional): if ``True``, :mod:`tqdm` will be
          used to show a progress bar for each epoch. If a string is given,
          the content of the string will be shown before the progress bar.
          If the module :mod:`tqdm` is not installed, this will be ignored.
          (default: None)
    """

    ON_BATCH_START = 'ON_BATCH_START'
    ON_BATCH_END = 'ON_BATCH_END'
    ON_EPOCH_START = 'ON_EPOCH_START'
    ON_EPOCH_END = 'ON_EPOCH_END'

    _logger = log.get_logger(__name__)

    def __init__(self, model, data_loader,
                 batch_input_fn=None,
                 batch_target_fn=None,
                 progress_bar=None):
        self._model = model
        self._data_loader = data_loader
        self._batch_input_fn = batch_input_fn
        self._batch_target_fn = batch_target_fn
        self._progress_bar = progress_bar

        self._epochs = 0
        self._iterations = 0

        self._hooks = {
            self.ON_BATCH_START: [],
            self.ON_EPOCH_START: [],
            self.ON_BATCH_END: [],
            self.ON_EPOCH_END: []
        }

        if progress_bar and not tqdm:
            _logger.debug('A progress cannot be shown because'
                          'the "tqdm" module was not found.')

    @property
    def batch_input_fn(self):
        return self._batch_input_fn

    @property
    def batch_target_fn(self):
        return self._batch_target_fn

    @property
    def model(self):
        return self._model

    @property
    def hooks(self):
        return self._hooks

    @property
    def epochs(self):
        return self._epochs

    @property
    def iterations(self):
        return self._iterations

    @property
    def logger(self):
        return self._logger

    def reset(self):
        r"""Reset the number of epochs and iterations run."""
        self._epochs = 0
        self._iterations = 0
        return self

    def set_batch_input_fn(self, fn):
        r"""Set the function to obtain the inputs for the model.

        The argument can be either a function or a callable object that
        will receive as a single argument the batch read from the
        ``data_loader``, and must return the appropriate input for the
        model.
        """
        assert fn is None or callable(fn)
        self._batch_input_fn = fn
        return self

    def set_batch_target_fn(self, fn):
        r"""Set the function to obtain the targets from the batch.

        The argument can be either a function or a callable object that
        will receive as a single argument the batch read from the
        ``data_loader``, it must return an appropriate object that the
        hooks can understand.
        """
        assert fn is None or callable(fn)
        self._batch_target_fn = fn
        return self

    def add_hook(self, when, func):
        r"""Add a hook function to be executed at some point during the run.

        When multiple hooks are added at the same point of the run, they will
        be run in order of addition.

        Args:
          when: point in the run (valid values: ``ON_BATCH_START``,
            ``ON_EPOCH_START``, ``ON_BATCH_END``, ``ON_EPOCH_END``).
          func: function or callable object that must accept ``**kwargs``.
        """
        assert when in self._hooks, (
            '{!r} is not a valid hook event'.format(when))
        self._hooks[when].append(func)
        return self

    def run(self):
        r"""Run a single epoch on the `dataset_loader`."""
        self._run_epoch()
        return self

    def _call_hooks(self, when, **kwargs):
        for hook in self._hooks[when]:
            hook(caller=self, **kwargs)

    def _run_iteration(self, it, batch):
        self._iterations += 1

        if self._batch_input_fn:
            batch_input = self._batch_input_fn(batch)
        else:
            batch_input = batch

        if self._batch_target_fn:
            batch_target = self._batch_target_fn(batch)
        else:
            batch_target = None

        self._call_hooks(self.ON_BATCH_START,
                         batch=batch,
                         batch_num=it,
                         epoch=self._epochs,
                         iteration=self._iterations,
                         batch_input=batch_input,
                         batch_target=batch_target)

        # Put model in evaluation mode
        if hasattr(self._model, 'eval'):
            self._model.eval()

        batch_output = self._model(batch_input)

        self._call_hooks(self.ON_BATCH_END,
                         batch=batch,
                         batch_num=it,
                         epoch=self._epochs,
                         iteration=self._iterations,
                         batch_input=batch_input,
                         batch_target=batch_target,
                         batch_output=batch_output)

    def _run_epoch(self):
        self._epochs += 1
        self._call_hooks(self.ON_EPOCH_START, epoch=self._epochs)

        if self._progress_bar and tqdm:
            if isinstance(self._progress_bar, string_classes):
                batch_iterator = tqdm(self._data_loader,
                                      desc=self._progress_bar)
            else:
                batch_iterator = tqdm(self._data_loader)
        else:
            batch_iterator = self._data_loader

        for it, batch in enumerate(batch_iterator, 1):
            self._run_iteration(it, batch)

        self._call_hooks(self.ON_EPOCH_END, epoch=self._epochs)


# If we decide to extend the Evaluator class, we can move it to
# a different file and extend from the Engine class, but
# right now an Evaluator is just a Engine.
Evaluator = Engine
