from laia.utils.symbols_table import SymbolsTable
import torch
import math
from scipy.misc import logsumexp


def unigram_phoc(sequence, unigram_map, unigram_levels,
                 ignore_missing=False):
    r"""Compute the Pyramid of Histograms of Characters (PHOC) of a given
    sequence of characters (or arbitrary symbols).

    Args:
      sequence (list, tuple, str): sequence of characters.
      unigram_map (dict): map from symbols to positions in the histogram.
      unigram_levels (list): list of levels in the pyramid.
      ignore_missing (bool): If True, will ignore elements the sequence not
         present in the unigram_map dictionary.

    Returns:
      A tuple representing the PHOC of the given sequence.
    """
    global _num_warnings

    def occupancy(i, n):
        return (float(i) / n, float(i + 1) / n)

    def overlap(a, b):
        return (max(a[0], b[0]), min(a[1], b[1]))

    def size(o):
        return o[1] - o[0]

    # Initialize histogram to 0
    phoc_size = len(unigram_map) * sum(unigram_levels)
    phoc = [0] * phoc_size

    # Offset of each unigram level starts in the PHOC array.
    level_offset = [0]
    for i, level in enumerate(unigram_levels[1:], 1):
        level_offset.append(
            level_offset[i - 1] +
            unigram_levels[i - 1] * len(unigram_map))

    # Compute PHOC
    num_chars = len(sequence)
    missing_count = {}  # This is not being used.
    for i, ch in enumerate(sequence):
        if ch not in unigram_map:
            if ignore_missing:
                missing_count[ch] = missing_count.get(ch, 0) + 1
                continue
            else:
                raise KeyError(
                    'Unigram {!r} was not found in the unigram map'.format(ch))
        ch_occ = occupancy(i, num_chars)
        for j, level in enumerate(unigram_levels):
            for region in range(level):
                region_occ = occupancy(region, level)
                if size(overlap(ch_occ, region_occ)) / size(ch_occ) >= 0.5:
                    # Total offset in the histogram for the current level,
                    # region and character.
                    z = (level_offset[j] +
                         region * len(unigram_map) +
                         unigram_map[ch])
                    phoc[z] = 1
    return tuple(phoc)


def probabilistic_phoc_relevance(a, b):
    """Compute the probabilistic PHOC relevance score.

    Args:
        a: vector of log-probabilities of the first sample, p(h_i = 1 | a)
        b: vector of log-probabilities of the second sample, p(h_i = 1 | b)

    Returns:
        p(R = 1 \mid a, b) = \sum_{h} p(h | a) p(h | b)
    """
    assert torch.is_tensor(a) and torch.is_tensor(b)
    a, b = a.cpu(), b.cpu()

    result = 0.0
    for i in range(a.size(0)):
        h1 = a[i] + b[i]
        h0 = math.log(-math.expm1(a[i])) + math.log(-math.expm1(b[i]))
        result += logsumexp([h0, h1])

    return result


class TextToPHOC(object):
    def __init__(self, syms, levels):
        assert isinstance(syms, (dict, SymbolsTable))
        assert isinstance(levels, (list, tuple))
        self._syms = syms
        self._levels = levels

    def __call__(self, x):
        return torch.Tensor(unigram_phoc(x, self._syms, self._levels))
