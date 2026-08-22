from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from machina.apps.forum.models import Forum
from machina.apps.forum_conversation.models import Post, Topic
from machina.apps.forum_permission.models import ForumPermission, UserForumPermission

from accounts.models import DeletedComment, PostReply, Profile

User = get_user_model()


class ReplyThreadTests(TestCase):
    """Covers the 대댓글 (reply-to-comment) threading feature."""

    @classmethod
    def setUpTestData(cls):
        cls.forum = Forum(name='자유', slug='free', type=Forum.FORUM_POST)
        cls.forum.insert_at(None, position='last-child', save=True)

        # Grant an authenticated user the permissions needed to post.
        perms = [
            'can_see_forum', 'can_read_forum', 'can_start_new_topics',
            'can_reply_to_topics', 'can_edit_own_posts', 'can_delete_own_posts',
            'can_post_without_approval',
        ]
        for codename in perms:
            perm = ForumPermission.objects.get(codename=codename)
            UserForumPermission.objects.create(
                permission=perm, forum=cls.forum,
                authenticated_user=True, has_perm=True,
            )

        cls.user = User.objects.create_user(username='tester', password='pw12345!')
        Profile.objects.create(user=cls.user, nickname='테스터')

        # A topic with its head post.
        cls.topic = Topic.objects.create(
            forum=cls.forum, poster=cls.user, subject='첫 글',
            type=Topic.TOPIC_POST, status=Topic.TOPIC_UNLOCKED, approved=True,
        )
        cls.head = Post.objects.create(
            topic=cls.topic, poster=cls.user, subject='첫 글', content='본문', approved=True,
        )

    def setUp(self):
        self.client.force_login(self.user)

    def _create_comment(self, content):
        url = reverse('forum_conversation:post_create', kwargs={
            'forum_slug': self.forum.slug, 'forum_pk': self.forum.pk,
            'topic_slug': self.topic.slug, 'topic_pk': self.topic.pk,
        })
        resp = self.client.post(url, {'subject': 'Re', 'content': content})
        self.assertEqual(resp.status_code, 302)
        return Post.objects.get(topic=self.topic, content=content)

    def _reply(self, parent, content):
        resp = self.client.post(
            reverse('reply_to_post', kwargs={'parent_id': parent.pk}),
            {'content': content},
        )
        self.assertEqual(resp.status_code, 302)
        return Post.objects.get(content=content)

    def test_reply_is_linked_to_parent_comment(self):
        parent = self._create_comment('부모 댓글')
        self._reply(parent, '첫 대댓글')
        self._reply(parent, '둘째 대댓글')

        self.assertEqual(PostReply.objects.filter(parent=parent).count(), 2)

    def test_replies_cascade(self):
        """A -> B -> C -> D each nest one level deeper under their own parent."""
        a = self._create_comment('A')
        b = self._reply(a, 'B')
        c = self._reply(b, 'C')
        d = self._reply(c, 'D')

        self.assertEqual(PostReply.objects.get(post=b).parent_id, a.pk)
        self.assertEqual(PostReply.objects.get(post=c).parent_id, b.pk)
        self.assertEqual(PostReply.objects.get(post=d).parent_id, c.pk)

    def test_cascade_stops_at_max_depth(self):
        """A reply to a level-4 comment stays at level 4 (sibling under level-3)."""
        a = self._create_comment('A')          # depth 0
        b = self._reply(a, 'B')                 # depth 1
        c = self._reply(b, 'C')                 # depth 2
        d = self._reply(c, 'D')                 # depth 3 (level 4, deepest)
        e = self._reply(d, 'E')                 # would be depth 4 -> capped

        # E hangs off C (D's parent), landing at the same level as D.
        self.assertEqual(PostReply.objects.get(post=e).parent_id, c.pk)

    def test_comment_thread_depth_and_order(self):
        from accounts.templatetags.community_tags import get_comment_thread

        a = self._create_comment('A')
        b = self._reply(a, 'B')
        self._reply(b, 'C')
        self._reply(a, 'B2')

        thread = get_comment_thread(self.topic)
        # Depth-first pre-order: A, B, C, B2.
        self.assertEqual(
            [(str(e['post'].content), e['depth']) for e in thread],
            [('A', 0), ('B', 1), ('C', 2), ('B2', 1)],
        )
        # Indentation scales with depth.
        self.assertEqual(thread[0]['indent'], 0)
        self.assertGreater(thread[2]['indent'], thread[1]['indent'])

    def _delete_comment(self, post):
        return self.client.post(reverse('delete_comment', kwargs={'post_id': post.pk}))

    def test_delete_comment_with_replies_becomes_tombstone(self):
        """Deleting a comment that still has replies keeps the post as a tombstone."""
        a = self._create_comment('A')
        self._reply(a, 'B')

        resp = self._delete_comment(a)
        self.assertEqual(resp.status_code, 302)

        # The post row survives, and its replies stay attached.
        self.assertTrue(Post.objects.filter(pk=a.pk).exists())
        self.assertTrue(DeletedComment.objects.filter(post=a).exists())
        self.assertEqual(PostReply.objects.filter(parent=a).count(), 1)

    def test_delete_leaf_comment_is_removed(self):
        """Deleting a comment with no replies removes it entirely."""
        a = self._create_comment('A')

        resp = self._delete_comment(a)
        self.assertEqual(resp.status_code, 302)

        self.assertFalse(Post.objects.filter(pk=a.pk).exists())
        self.assertFalse(DeletedComment.objects.filter(post=a).exists())

    def test_thread_marks_deleted_comment(self):
        from accounts.templatetags.community_tags import get_comment_thread

        a = self._create_comment('A')
        self._reply(a, 'B')
        self._delete_comment(a)

        thread = get_comment_thread(self.topic)
        entry = next(e for e in thread if e['post'].pk == a.pk)
        self.assertIsNotNone(entry['deleted'])
        self.assertEqual(entry['deleted'].deleted_by, self.user)
