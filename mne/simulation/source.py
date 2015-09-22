# Authors: Alexandre Gramfort <alexandre.gramfort@telecom-paristech.fr>
#          Martin Luessi <mluessi@nmr.mgh.harvard.edu>
#          Daniel Strohmeier <daniel.strohmeier@tu-ilmenau.de>
#
# License: BSD (3-clause)

import numpy as np

from ..source_estimate import SourceEstimate
from ..utils import check_random_state, deprecated, logger
from ..externals.six.moves import zip


def select_source_in_label(src, label, random_state=None):
    """Select source positions using a label

    Parameters
    ----------
    src : list of dict
        The source space
    label : Label
        the label (read with mne.read_label)
    random_state : None | int | np.random.RandomState
        To specify the random generator state.

    Returns
    -------
    lh_vertno : list
        selected source coefficients on the left hemisphere
    rh_vertno : list
        selected source coefficients on the right hemisphere
    """
    lh_vertno = list()
    rh_vertno = list()

    rng = check_random_state(random_state)

    if label.hemi == 'lh':
        src_sel_lh = np.intersect1d(src[0]['vertno'], label.vertices)
        idx_select = rng.randint(0, len(src_sel_lh), 1)
        lh_vertno.append(src_sel_lh[idx_select][0])
    else:
        src_sel_rh = np.intersect1d(src[1]['vertno'], label.vertices)
        idx_select = rng.randint(0, len(src_sel_rh), 1)
        rh_vertno.append(src_sel_rh[idx_select][0])

    return lh_vertno, rh_vertno


@deprecated('"generate_sparse_stc" is deprecated and will be removed in'
            'MNE-0.11. Please use simulate_sparse_stc instead')
def generate_sparse_stc(src, labels, stc_data, tmin, tstep, random_state=None):
    """Generate sparse sources time courses from waveforms and labels

    This function randomly selects a single vertex in each label and assigns
    a waveform from stc_data to it.

    Parameters
    ----------
    src : list of dict
        The source space
    labels : list of Labels
        The labels
    stc_data : array (shape: len(labels) x n_times)
        The waveforms
    tmin : float
        The beginning of the timeseries
    tstep : float
        The time step (1 / sampling frequency)
    random_state : None | int | np.random.RandomState
        To specify the random generator state.

    Returns
    -------
    stc : SourceEstimate
        The generated source time courses.
    """
    if len(labels) != len(stc_data):
        raise ValueError('labels and stc_data must have the same length')

    rng = check_random_state(random_state)
    vertno = [[], []]
    lh_data = list()
    rh_data = list()
    for label_data, label in zip(stc_data, labels):
        lh_vertno, rh_vertno = select_source_in_label(src, label, rng)
        vertno[0] += lh_vertno
        vertno[1] += rh_vertno
        if len(lh_vertno) != 0:
            lh_data.append(np.atleast_2d(label_data))
        elif len(rh_vertno) != 0:
            rh_data.append(np.atleast_2d(label_data))
        else:
            raise ValueError('No vertno found.')

    vertno = [np.array(v) for v in vertno]

    # the data is in the order left, right
    data = list()
    if len(vertno[0]) != 0:
        idx = np.argsort(vertno[0])
        vertno[0] = vertno[0][idx]
        data.append(np.concatenate(lh_data)[idx])

    if len(vertno[1]) != 0:
        idx = np.argsort(vertno[1])
        vertno[1] = vertno[1][idx]
        data.append(np.concatenate(rh_data)[idx])

    data = np.concatenate(data)

    stc = SourceEstimate(data, vertices=vertno, tmin=tmin, tstep=tstep)

    return stc


def simulate_sparse_stc(src, n_dipoles, times,
                        data_fun=lambda t: 1e-7 * np.sin(20 * np.pi * t),
                        labels=None, random_state=None):
    """Generate sparse (n_dipoles) sources time courses from data_fun

    This function randomly selects n_dipoles vertices in the whole cortex
    or one single vertex in each label if labels is not None. It uses data_fun
    to generate waveforms for each vertex.

    Parameters
    ----------
    src : list of dict
        The source space.
    n_dipoles : int
        Number of dipoles to simulate.
    times : array
        Time array
    data_fun : callable
        Function to generate the waveforms. The default is a 100 nAm, 10 Hz
        sinusoid as ``1e-7 * np.sin(20 * pi * t)``. The function should take
        as input the array of time samples in seconds and return an array of
        the same length containing the time courses.
    labels : None | list of Labels
        The labels. The default is None, otherwise its size must be n_dipoles.
    random_state : None | int | np.random.RandomState
        To specify the random generator state.

    Returns
    -------
    stc : SourceEstimate
        The generated source time courses.

    Notes
    -----
    .. versionadded:: 0.10.0
    """
    rng = check_random_state(random_state)

    data = np.zeros((n_dipoles, len(times)))
    for i_dip in range(n_dipoles):
        data[i_dip, :] = data_fun(times)

    if labels is None:
        n_dipoles_lh = n_dipoles // 2
        n_dipoles_rh = n_dipoles - n_dipoles_lh

        # ensure unique vertex sets
        vertno_lh = rng.permutation(np.arange(len(src[0]['vertno'])))
        vertno_lh = np.sort(vertno_lh[:n_dipoles_lh])
        vertno_rh = rng.permutation(np.arange(len(src[1]['vertno'])))
        vertno_rh = np.sort(vertno_rh[:n_dipoles_rh])
        vertno = [src[0]['vertno'][[vertno_lh]], src[1]['vertno'][[vertno_rh]]]

        lh_data = list(data[:n_dipoles_lh])
        rh_data = list(data[n_dipoles_lh:])
    else:
        if n_dipoles != len(labels):
            logger.warning('The number of labels is different from the number '
                           'of dipoles. %s dipole(s) will be generated.'
                           % min(n_dipoles, len(labels)))
        labels = labels[:n_dipoles] if n_dipoles < len(labels) else labels

        vertno = [[], []]
        lh_data = list()
        rh_data = list()
        for i, label in enumerate(labels):
            lh_vertno, rh_vertno = select_source_in_label(src, label, rng)
            vertno[0] += lh_vertno
            vertno[1] += rh_vertno
            if len(lh_vertno) != 0:
                lh_data.append(np.atleast_2d(data[i]))
            elif len(rh_vertno) != 0:
                rh_data.append(np.atleast_2d(data[i]))
            else:
                raise ValueError('No vertno found.')
        vertno = [np.array(v, dtype='int64') for v in vertno]
        lh_data, rh_data = [np.concatenate(dd) if len(dd) != 0 else []
                            for dd in [lh_data, rh_data]]

    # the data is in the order left, right
    data = list()
    if len(vertno[0]) != 0:
        idx = np.argsort(vertno[0])
        vertno[0] = vertno[0][idx]
        data.append(np.array(lh_data)[idx])

    if len(vertno[1]) != 0:
        idx = np.argsort(vertno[1])
        vertno[1] = vertno[1][idx]
        data.append(np.array(rh_data)[idx])

    data = np.array(np.concatenate(data))

    tmin, tstep = times[0], np.diff(times)[0]
    stc = SourceEstimate(data, vertices=vertno, tmin=tmin, tstep=tstep)

    return stc


@deprecated('"generate_stc" is deprecated and will be removed in'
            'MNE-0.11. Please use simulate_sparse_stc instead')
def generate_stc(src, labels, stc_data, tmin, tstep, value_fun=None):
    """Generate sources time courses from waveforms and labels

    This function generates a source estimate with extended sources by
    filling the labels with the waveforms given in stc_data.

    By default, the vertices within a label are assigned the same waveform.
    The waveforms can be scaled for each vertex by using the label values
    and value_fun. E.g.,

    # create a source label where the values are the distance from the center
    labels = circular_source_labels('sample', 0, 10, 0)

    # sources with decaying strength (x will be the distance from the center)
    fun = lambda x: exp(- x / 10)
    stc = generate_stc(fwd, labels, stc_data, tmin, tstep, fun)

    Parameters
    ----------
    src : list of dict
        The source space
    labels : list of Labels
        The labels
    stc_data : array (shape: len(labels) x n_times)
        The waveforms
    tmin : float
        The beginning of the timeseries
    tstep : float
        The time step (1 / sampling frequency)
    value_fun : function
        Function to apply to the label values

    Returns
    -------
    stc : SourceEstimate
        The generated source time courses.
    """

    if len(labels) != len(stc_data):
        raise ValueError('labels and stc_data must have the same length')

    vertno = [[], []]
    stc_data_extended = [[], []]
    hemi_to_ind = {'lh': 0, 'rh': 1}
    for i, label in enumerate(labels):
        hemi_ind = hemi_to_ind[label.hemi]
        src_sel = np.intersect1d(src[hemi_ind]['vertno'],
                                 label.vertices)
        if value_fun is not None:
            idx_sel = np.searchsorted(label.vertices, src_sel)
            values_sel = np.array([value_fun(v) for v in
                                   label.values[idx_sel]])

            data = np.outer(values_sel, stc_data[i])
        else:
            data = np.tile(stc_data[i], (len(src_sel), 1))

        vertno[hemi_ind].append(src_sel)
        stc_data_extended[hemi_ind].append(np.atleast_2d(data))

    # format the vertno list
    for idx in (0, 1):
        if len(vertno[idx]) > 1:
            vertno[idx] = np.concatenate(vertno[idx])
        elif len(vertno[idx]) == 1:
            vertno[idx] = vertno[idx][0]
    vertno = [np.array(v) for v in vertno]

    # the data is in the order left, right
    data = list()
    if len(vertno[0]) != 0:
        idx = np.argsort(vertno[0])
        vertno[0] = vertno[0][idx]
        data.append(np.concatenate(stc_data_extended[0])[idx])

    if len(vertno[1]) != 0:
        idx = np.argsort(vertno[1])
        vertno[1] = vertno[1][idx]
        data.append(np.concatenate(stc_data_extended[1])[idx])

    data = np.concatenate(data)

    stc = SourceEstimate(data, vertices=vertno, tmin=tmin, tstep=tstep)
    return stc
