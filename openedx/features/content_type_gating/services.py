"""
Content Type Gating service.
"""
import crum

from lms.djangoapps.courseware.access import has_access
from lms.djangoapps.courseware.masquerade import (
    is_masquerading_as_limited_access, is_masquerading_as_audit_enrollment,
)
from openedx.core.lib.graph_traversals import get_children, leaf_filter, traverse_pre_order
from openedx.features.content_type_gating.helpers import CONTENT_GATING_PARTITION_ID, FULL_ACCESS, LIMITED_ACCESS
from openedx.features.content_type_gating.models import ContentTypeGatingConfig
from openedx.features.content_type_gating.partitions import create_content_gating_partition


class ContentTypeGatingService(object):
    """
    Content Type Gating uses Block Transformers to gate sections of the course outline
    and field overrides to gate course content.
    This service was created as a helper class for handling timed exams that contain content type gated problems.
    """
    def _enabled_for_enrollment(self, **kwargs):
        """
        Returns whether content type gating is enabled for a given user/course pair
        """
        return ContentTypeGatingConfig.enabled_for_enrollment(**kwargs)

    def _is_masquerading_as_audit_or_limited_access(self, user, course_id):
        return (is_masquerading_as_limited_access(user, course_id) or
                is_masquerading_as_audit_enrollment(user, course_id))

    def _get_user(self):
        """
        Return the current request user.
        """
        return crum.get_current_user()

    def _content_type_gate_for_block(self, user, block, course, course_id):
        """
        Returns a Fragment of the content type gate (if any) that would appear for a given block
        """
        problem_eligible_for_content_gating = (getattr(block, 'graded', False) and
                                               block.has_score and
                                               getattr(block, 'weight', 0) != 0)
        if problem_eligible_for_content_gating:
            access = has_access(user, 'load', block, course_id)
            if (not access and access.error_code == 'incorrect_user_group'):
                return access.user_fragment

            # Handle case of staff users masquerading as Learner in Audit or Learner in Limited Access
            if self._is_masquerading_as_audit_or_limited_access(user, course_id):
                # Check merged_group_access in case the course steam overrode content type gating
                # for this problem with the studio override
                if LIMITED_ACCESS.id not in block.merged_group_access.get(CONTENT_GATING_PARTITION_ID):
                    return create_content_gating_partition(course).access_denied_fragment(
                        course, user, LIMITED_ACCESS, [FULL_ACCESS]
                    )
            return None

    def check_children_for_content_type_gating_paywall(self, item, course, course_id):
        """
        Arguments:
            item (xblock such as a sequence or vertical block)
            course (xblock.internal.CourseDescriptorWithMixins)
            course_id (CourseLocator)

        Returns:
            If:
            This xblock contains problems which this user cannot load due to content type gating
            Then:
            Return the first content type gating paywall (Fragment)
            Else:
            Return None
        """
        user = self._get_user()
        if user:
            if not self._enabled_for_enrollment(user=user, course_key=course_id):
                return None

            # Check children for content type gated content
            for block in traverse_pre_order(item, get_children, leaf_filter):
                gate_fragment = self._content_type_gate_for_block(user, block, course, course_id)
                if gate_fragment is not None:
                    return gate_fragment.content
        return None
