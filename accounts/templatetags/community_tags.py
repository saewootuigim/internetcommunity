from django import template

from machina.core.db.models import get_model

from accounts.models import TopicVote, PostReply, DeletedComment

Topic = get_model('forum_conversation', 'Topic')
Post = get_model('forum_conversation', 'Post')

register = template.Library()


@register.filter
def subtract(value, arg):
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return value


@register.simple_tag
def get_recent_topics(forum, count=5):
    return (
        Topic.objects.filter(forum=forum, approved=True)
        .select_related('poster', 'poster__profile')
        .order_by('-created')[:count]
    )


@register.simple_tag
def get_topic_votes(topic):
    up = TopicVote.objects.filter(topic=topic, vote=1).count()
    down = TopicVote.objects.filter(topic=topic, vote=-1).count()
    return {'up': up, 'down': down}


# Maximum nesting level for cascading replies (1-indexed: level 4 is the last
# level that gets its own indentation). A reply to a level-4 comment becomes a
# sibling at level 4 instead of nesting deeper.
MAX_REPLY_DEPTH = 4
# Horizontal indent (in rem) added per nesting level — matches B's offset from A.
INDENT_PER_LEVEL = 1.5


@register.simple_tag
def get_comment_thread(topic):
    """Return the topic's comments as a flat, pre-ordered threaded list.

    The topic-head post is excluded. Each entry is a dict:
        {'post': <comment>, 'depth': <0-based nesting level>, 'indent': <rem>}
    Comments are emitted in depth-first pre-order: a comment is followed by its
    replies (ordered by creation), each nested one level deeper.
    """
    posts = list(
        topic.posts.filter(approved=True)
        .select_related('poster', 'poster__profile', 'updated_by')
        .order_by('created')
    )
    # Drop the topic head (the original post shown separately).
    head_id = topic.first_post_id
    comments = [p for p in posts if p.pk != head_id]
    comment_ids = {p.pk for p in comments}

    parent_map = dict(
        PostReply.objects.filter(post__topic=topic).values_list('post_id', 'parent_id')
    )

    # Tombstones for soft-deleted comments (kept because they still have replies).
    deletions = {
        d.post_id: d for d in DeletedComment.objects.filter(post__topic=topic)
        .select_related('deleted_by')
    }

    # Group each comment under its parent (roots = comments with no parent
    # comment). Insertion order follows creation, so children stay chronological.
    children_by_parent = {}
    roots = []
    for post in comments:
        parent_id = parent_map.get(post.pk)
        if parent_id and parent_id in comment_ids:
            children_by_parent.setdefault(parent_id, []).append(post)
        else:
            roots.append(post)

    op_id = topic.poster_id
    thread = []

    def walk(post, depth, parent):
        thread.append({
            'post': post,
            'parent': parent,          # parent comment (None for top-level)
            'depth': depth,
            'indent': depth * INDENT_PER_LEVEL,
            'is_op': post.poster_id is not None and post.poster_id == op_id,
            'deleted': deletions.get(post.pk),
        })
        for child in children_by_parent.get(post.pk, []):
            walk(child, depth + 1, post)

    for root in roots:
        walk(root, 0, None)
    return thread
