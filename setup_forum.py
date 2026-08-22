import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'community.settings')
django.setup()

from machina.apps.forum.models import Forum
from machina.apps.forum_permission.models import ForumPermission, GroupForumPermission, UserForumPermission

forum = Forum(
    name='자유',
    slug='free',
    description='자유롭게 이야기하는 게시판',
    type=Forum.FORUM_POST,
)
forum.insert_at(None, position='last-child', save=True)
print(f'Created forum: id={forum.pk}, slug={forum.slug}')

# Set permissions: anonymous can read, authenticated can post
perms_to_grant_anonymous = [
    'can_see_forum',
    'can_read_forum',
]

perms_to_grant_authenticated = [
    'can_see_forum',
    'can_read_forum',
    'can_start_new_topics',
    'can_reply_to_topics',
    'can_edit_own_posts',
    'can_delete_own_posts',
    'can_post_without_approval',
]

for codename in perms_to_grant_anonymous:
    perm = ForumPermission.objects.get(codename=codename)
    UserForumPermission.objects.create(
        permission=perm,
        forum=forum,
        anonymous_user=True,
        has_perm=True,
    )

for codename in perms_to_grant_authenticated:
    perm = ForumPermission.objects.get(codename=codename)
    UserForumPermission.objects.create(
        permission=perm,
        forum=forum,
        authenticated_user=True,
        has_perm=True,
    )

print('Permissions configured.')
