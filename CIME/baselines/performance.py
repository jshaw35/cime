import os
import glob
import re
import gzip
import logging
from CIME.config import Config
from CIME.utils import expect, get_src_root, get_current_commit, get_timestamp

logger = logging.getLogger(__name__)


def perf_compare_throughput_baseline(case, baseline_dir=None):
    """
    Compares model throughput.

    Parameters
    ----------
    case : CIME.case.case.Case
        Current case object.
    baseline_dir : str
        Overrides the baseline directory.

    Returns
    -------
    below_tolerance : bool
        Whether the comparison was below the tolerance.
    comment : str
        Provides explanation from comparison.
    """
    if baseline_dir is None:
        baseline_dir = case.get_baseline_dir()

    config = load_coupler_customization(case)

    baseline_file = os.path.join(baseline_dir, "cpl-tput.log")

    baseline = read_baseline_file(baseline_file)

    tolerance = case.get_value("TEST_TPUT_TOLERANCE")

    if tolerance is None:
        tolerance = 0.1

    expect(
        tolerance > 0.0,
        "Bad value for throughput tolerance in test",
    )

    try:
        below_tolerance, comment = config.perf_compare_throughput_baseline(
            case, baseline, tolerance
        )
    except AttributeError:
        below_tolerance, comment = _perf_compare_throughput_baseline(
            case, baseline, tolerance
        )

    return below_tolerance, comment


def perf_compare_memory_baseline(case, baseline_dir=None):
    """
    Compares model highwater memory usage.

    Parameters
    ----------
    case : CIME.case.case.Case
        Current case object.
    baseline_dir : str
        Overrides the baseline directory.

    Returns
    -------
    below_tolerance : bool
        Whether the comparison was below the tolerance.
    comment : str
        Provides explanation from comparison.
    """
    if baseline_dir is None:
        baseline_dir = case.get_baseline_dir()

    config = load_coupler_customization(case)

    baseline_file = os.path.join(baseline_dir, "cpl-mem.log")

    baseline = read_baseline_file(baseline_file)

    tolerance = case.get_value("TEST_MEMLEAK_TOLERANCE")

    if tolerance is None:
        tolerance = 0.1

    try:
        below_tolerance, comments = config.perf_compare_memory_baseline(
            case, baseline, tolerance
        )
    except AttributeError:
        below_tolerance, comments = _perf_compare_memory_baseline(
            case, baseline, tolerance
        )

    return below_tolerance, comments


def perf_write_baseline(case, basegen_dir, throughput=True, memory=True):
    """
    Writes the baseline performance files.

    Parameters
    ----------
    case : CIME.case.case.Case
        Current case object.
    basegen_dir : str
        Path to baseline directory.
    throughput : bool
        If true, write throughput baseline.
    memory : bool
        If true, write memory baseline.
    """
    config = load_coupler_customization(case)

    if throughput:
        try:
            tput = perf_get_throughput(case, config)
        except RuntimeError as e:
            logger.debug("Could not get throughput: {0!s}".format(e))
        else:
            baseline_file = os.path.join(basegen_dir, "cpl-tput.log")

            write_baseline_file(baseline_file, tput)

            logger.info("Updated throughput baseline to {!s}".format(tput))

    if memory:
        try:
            mem = perf_get_memory(case, config)
        except RuntimeError as e:
            logger.info("Could not get memory usage: {0!s}".format(e))
        else:
            baseline_file = os.path.join(basegen_dir, "cpl-mem.log")

            write_baseline_file(baseline_file, mem)

            logger.info("Updated memory usage baseline to {!s}".format(mem))


def load_coupler_customization(case):
    """
    Loads customizations from the coupler `cime_config` directory.

    Parameters
    ----------
    case : CIME.case.case.Case
        Current case object.

    Returns
    -------
    CIME.config.Config
        Runtime configuration.
    """
    comp_root_dir_cpl = case.get_value("COMP_ROOT_DIR_CPL")

    cpl_customize = os.path.join(comp_root_dir_cpl, "cime_config", "customize")

    return Config.load(cpl_customize)


def perf_get_throughput(case, config):
    """
    Gets the model throughput.

    First attempts to use a coupler define method to retrieve the
    models throughput. If this is not defined then the default
    method of parsing the coupler log is used.

    Parameters
    ----------
    case : CIME.case.case.Case
        Current case object.

    Returns
    -------
    str or None
        Model throughput.
    """
    try:
        tput = config.perf_get_throughput(case)
    except AttributeError:
        tput = _perf_get_throughput(case)

        if tput is None:
            raise RuntimeError("Could not get default throughput") from None

        tput = str(tput)

    return tput


def perf_get_memory(case, config):
    """
    Gets the model memory usage.

    First attempts to use a coupler defined method to retrieve the
    models memory usage. If this is not defined then the default
    method of parsing the coupler log is used.

    Parameters
    ----------
    case : CIME.case.case.Case
        Current case object.

    Returns
    -------
    str or None
        Model memory usage.
    """
    try:
        mem = config.perf_get_memory(case)
    except AttributeError:
        mem = _perf_get_memory(case)

        if mem is None:
            raise RuntimeError("Could not get default memory usage") from None

        mem = str(mem[-1][1])

    return mem


def write_baseline_file(baseline_file, value):
    """
    Writes value to `baseline_file`.

    Parameters
    ----------
    baseline_file : str
        Path to the baseline file.
    value : str
        Value to write.
    """
    commit_hash = get_current_commit(repo=get_src_root())

    timestamp = get_timestamp(timestamp_format="%Y-%m-%d_%H:%M:%S")

    with open(baseline_file, "w") as fd:
        fd.write(f"# sha:{commit_hash} date: {timestamp}\n")
        fd.write(value)


def _perf_get_memory(case, cpllog=None):
    """
    Default function to retrieve memory usage from the coupler log.

    If the usage is not available from the log then `None` is returned.

    Parameters
    ----------
    case : CIME.case.case.Case
        Current case object.
    cpllog : str
        Overrides the default coupler log.

    Returns
    -------
    str or None
        Model memory usage or `None`.

    Raises
    ------
    RuntimeError
        If not enough sample were found.
    """
    if cpllog is None:
        cpllog = get_latest_cpl_logs(case)
    else:
        cpllog = [
            cpllog,
        ]

    try:
        memlist = get_cpl_mem_usage(cpllog[0])
    except (FileNotFoundError, IndexError):
        memlist = None

        logger.debug("Could not parse memory usage from coupler log")
    else:
        if len(memlist) <= 3:
            raise RuntimeError(
                f"Found {len(memlist)} memory usage samples, need atleast 4"
            )

    return memlist


def _perf_get_throughput(case):
    """
    Default function to retrieve throughput from the coupler log.

    If the throughput is not available from the log then `None` is returned.

    Parameters
    ----------
    case : CIME.case.case.Case
        Current case object.

    Returns
    -------
    str or None
        Model throughput or `None`.
    """
    cpllog = get_latest_cpl_logs(case)

    try:
        tput = get_cpl_throughput(cpllog[0])
    except (FileNotFoundError, IndexError):
        tput = None

        logger.debug("Could not parse throughput from coupler log")

    return tput


def get_latest_cpl_logs(case):
    """
    find and return the latest cpl log file in the run directory
    """
    coupler_log_path = case.get_value("RUNDIR")

    cpllog_name = "drv" if case.get_value("COMP_INTERFACE") == "nuopc" else "cpl"

    cpllogs = glob.glob(os.path.join(coupler_log_path, "{}*.log.*".format(cpllog_name)))

    lastcpllogs = []

    if cpllogs:
        lastcpllogs.append(max(cpllogs, key=os.path.getctime))

        basename = os.path.basename(lastcpllogs[0])

        suffix = basename.split(".", 1)[1]

        for log in cpllogs:
            if log in lastcpllogs:
                continue

            if log.endswith(suffix):
                lastcpllogs.append(log)

    return lastcpllogs


def get_cpl_mem_usage(cpllog):
    """
    Read memory usage from coupler log.

    Parameters
    ----------
    cpllog : str
        Path to the coupler log.

    Returns
    -------
    list
        Memory usage (data, highwater) as recorded by the coupler or empty list.
    """
    memlist = []

    meminfo = re.compile(r".*model date =\s+(\w+).*memory =\s+(\d+\.?\d+).*highwater")

    if cpllog is not None and os.path.isfile(cpllog):
        if ".gz" == cpllog[-3:]:
            fopen = gzip.open
        else:
            fopen = open

        with fopen(cpllog, "rb") as f:
            for line in f:
                m = meminfo.match(line.decode("utf-8"))

                if m:
                    memlist.append((float(m.group(1)), float(m.group(2))))

    # Remove the last mem record, it's sometimes artificially high
    if len(memlist) > 0:
        memlist.pop()

    return memlist


def get_cpl_throughput(cpllog):
    """
    Reads throuhgput from coupler log.

    Parameters
    ----------
    cpllog : str
        Path to the coupler log.

    Returns
    -------
    int or None
        Throughput as recorded by the coupler or None
    """
    if cpllog is not None and os.path.isfile(cpllog):
        with gzip.open(cpllog, "rb") as f:
            cpltext = f.read().decode("utf-8")

            m = re.search(r"# simulated years / cmp-day =\s+(\d+\.\d+)\s", cpltext)

            if m:
                return float(m.group(1))
    return None


def read_baseline_file(baseline_file):
    """
    Reads value from `baseline_file`.

    Strips comments and returns the raw content to be decoded.

    Parameters
    ----------
    baseline_file : str
        Path to the baseline file.

    Returns
    -------
    str
        Value stored in baseline file without comments.
    """
    with open(baseline_file) as fd:
        lines = [x.strip() for x in fd.readlines() if not x.startswith("#")]

    return "\n".join(lines)


def _perf_compare_throughput_baseline(case, baseline, tolerance):
    """
    Default throughput baseline comparison.

    Compares the throughput from the coupler to the baseline value.

    Parameters
    ----------
    case : CIME.case.case.Case
        Current case object.
    baseline : list
        Lines contained in the baseline file.
    tolerance : float
        Allowed tolerance for comparison.

    Returns
    -------
    below_tolerance : bool
        Whether the comparison was below the tolerance.
    comment : str
        provides explanation from comparison.
    """
    current = _perf_get_throughput(case)

    try:
        # default baseline is stored as single float
        baseline = float(baseline)
    except ValueError:
        comment = "Could not compare throughput to baseline, as basline had no value."

        return None, comment

    # comparing ypd so bigger is better
    diff = (baseline - current) / baseline

    below_tolerance = None

    if diff is not None:
        below_tolerance = diff < tolerance

        if below_tolerance:
            comment = "TPUTCOMP: Computation time changed by {:.2f}% relative to baseline".format(
                diff * 100
            )
        else:
            comment = "Error: TPUTCOMP: Computation time increase > {:d}% from baseline".format(
                int(tolerance * 100)
            )

    return below_tolerance, comment


def _perf_compare_memory_baseline(case, baseline, tolerance):
    """
    Default memory usage baseline comparison.

    Compares the highwater memory usage from the coupler to the baseline value.

    Parameters
    ----------
    case : CIME.case.case.Case
        Current case object.
    baseline : list
        Lines contained in the baseline file.
    tolerance : float
        Allowed tolerance for comparison.

    Returns
    -------
    below_tolerance : bool
        Whether the comparison was below the tolerance.
    comment : str
        provides explanation from comparison.
    """
    try:
        current = _perf_get_memory(case)
    except RuntimeError as e:
        return None, str(e)
    else:
        current = current[-1][1]

    try:
        # default baseline is stored as single float
        baseline = float(baseline)
    except ValueError:
        baseline = 0.0

    try:
        diff = (current - baseline) / baseline
    except ZeroDivisionError:
        diff = 0.0

    # Should we check if tolerance is above 0
    below_tolerance = None
    comment = ""

    if diff is not None:
        below_tolerance = diff < tolerance

        if below_tolerance:
            comment = "MEMCOMP: Memory usage highwater has changed by {:.2f}% relative to baseline".format(
                diff * 100
            )
        else:
            comment = "Error: Memory usage increase >{:d}% from baseline's {:f} to {:f}".format(
                int(tolerance * 100), baseline, current
            )

    return below_tolerance, comment
