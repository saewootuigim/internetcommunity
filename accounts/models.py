from django.conf import settings
from django.db import models


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    nickname = models.CharField(max_length=30, unique=True, verbose_name='별명')
    login_count = models.PositiveIntegerField(default=0)
    previous_login = models.DateTimeField(null=True, blank=True)
    current_login = models.DateTimeField(null=True, blank=True)
    nickname_changed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.nickname


class TopicVote(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    topic = models.ForeignKey('forum_conversation.Topic', on_delete=models.CASCADE, related_name='votes')
    vote = models.SmallIntegerField()  # +1 or -1
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'topic')


class PostReply(models.Model):
    """Maps a machina Post to its parent comment (one-level threading / 대댓글)."""
    post = models.OneToOneField(
        'forum_conversation.Post', on_delete=models.CASCADE, related_name='reply_link')
    parent = models.ForeignKey(
        'forum_conversation.Post', on_delete=models.CASCADE, related_name='child_replies')

    class Meta:
        indexes = [models.Index(fields=['parent'])]


class DeletedComment(models.Model):
    """Soft-delete tombstone for a comment that still has replies.

    The machina Post row is kept (so its 대댓글 stay nested beneath it), but its
    body is replaced by a tombstone. Poster and creation date remain visible.
    """
    post = models.OneToOneField(
        'forum_conversation.Post', on_delete=models.CASCADE, related_name='deletion')
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    deleted_at = models.DateTimeField(auto_now_add=True)
