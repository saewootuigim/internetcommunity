from django.core.management.base import BaseCommand

from machina.apps.forum.models import Forum
from machina.apps.forum_permission.models import ForumPermission, UserForumPermission


# Default board created on every deploy if no forum exists yet.
FORUM_NAME = '자유게시판'
FORUM_SLUG = 'free'

ANON_PERMS = [
    'can_see_forum',
    'can_read_forum',
]
AUTH_PERMS = [
    'can_see_forum',
    'can_read_forum',
    'can_start_new_topics',
    'can_reply_to_topics',
    'can_edit_own_posts',
    'can_delete_own_posts',
    'can_post_without_approval',
]


class Command(BaseCommand):
    help = (
        'Ensure a default 자유게시판 forum exists with sensible permissions. '
        'Idempotent: safe to run on every deploy.'
    )

    def handle(self, *args, **options):
        # If any forum already exists, do nothing (an admin has taken over).
        if Forum.objects.exists():
            self.stdout.write('A forum already exists; skipping default board creation.')
            return

        forum = Forum(name=FORUM_NAME, slug=FORUM_SLUG, type=Forum.FORUM_POST)
        forum.insert_at(None, position='last-child', save=True)

        self._grant(forum, ANON_PERMS, anonymous_user=True)
        self._grant(forum, AUTH_PERMS, authenticated_user=True)

        self.stdout.write(self.style.SUCCESS(
            f'Created default forum "{FORUM_NAME}" (id={forum.pk}).'
        ))

    def _grant(self, forum, codenames, **who):
        for codename in codenames:
            perm = ForumPermission.objects.get(codename=codename)
            UserForumPermission.objects.get_or_create(
                permission=perm, forum=forum, has_perm=True, **who,
            )
