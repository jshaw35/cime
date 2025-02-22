"""
Implementation of the CIME NCK test: Tests multi-instance

This does two runs: In the first, we use one instance per component; in the
second, we use two instances per components. NTASKS are changed in each run so
that the number of tasks per instance is the same for both runs.

Lay all of the components out sequentially
"""

from CIME.XML.standard_module_setup import *
from CIME.SystemTests.system_tests_compare_two import SystemTestsCompareTwo

logger = logging.getLogger(__name__)


class NCK(SystemTestsCompareTwo):
    def __init__(self, case, **kwargs):
        self._comp_classes = []
        SystemTestsCompareTwo.__init__(
            self,
            case,
            separate_builds=True,
            run_two_suffix="multiinst",
            run_one_description="one instance",
            run_two_description="two instances",
            **kwargs,
        )

    def _common_setup(self):
        # We start by halving the number of tasks for both cases. This ensures
        # that we use the same number of tasks per instance in both cases: For
        # the two-instance case, we'll double this halved number, so you may
        # think that the halving was unnecessary; but it's needed in case the
        # original NTASKS was odd. (e.g., for NTASKS originally 15, we want to
        # use NTASKS = int(15/2) * 2 = 14 tasks for case two.)
        self._comp_classes = self._case.get_values("COMP_CLASSES")
        self._comp_classes.remove("CPL")
        for comp in self._comp_classes:
            ntasks = self._case.get_value("NTASKS_{}".format(comp))
            if ntasks > 1:
                self._case.set_value("NTASKS_{}".format(comp), int(ntasks / 2))
            # the following assures that both cases use the same number of total tasks
            rootpe = self._case.get_value("ROOTPE_{}".format(comp))
            if rootpe > 1:
                self._case.set_value("ROOTPE_{}".format(comp), int(rootpe + ntasks / 2))

    def _case_one_setup(self):
        for comp in self._comp_classes:
            self._case.set_value("NINST_{}".format(comp), 1)

    def _case_two_setup(self):
        for comp in self._comp_classes:
            if comp == "ESP":
                self._case.set_value("NINST_{}".format(comp), 1)
            else:
                self._case.set_value("NINST_{}".format(comp), 2)

            ntasks = self._case.get_value("NTASKS_{}".format(comp))
            rootpe = self._case.get_value("ROOTPE_{}".format(comp))
            if rootpe > 1:
                self._case.set_value("ROOTPE_{}".format(comp), int(rootpe - ntasks))
            self._case.set_value("NTASKS_{}".format(comp), ntasks * 2)
        self._case.case_setup(test_mode=True, reset=True)
