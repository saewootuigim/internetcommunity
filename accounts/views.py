from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404

from .models import Profile, TopicVote, PostReply


def signup(request):
    if request.method == 'POST':
        from django.contrib.auth.forms import UserCreationForm
        form = UserCreationForm(request.POST)
        nickname = request.POST.get('nickname', '').strip()
        if not nickname:
            request.session['signup_errors'] = {'nickname': ['별명을 입력해주세요.']}
            return redirect('forum:index')
        if Profile.objects.filter(nickname=nickname).exists():
            request.session['signup_errors'] = {'nickname': ['이미 사용 중인 별명입니다.']}
            return redirect('forum:index')
        if form.is_valid():
            user = form.save()
            Profile.objects.create(user=user, nickname=nickname)
            login(request, user)
            return redirect('forum:index')
        request.session['signup_errors'] = dict(form.errors)
    return redirect('forum:index')


def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            profile, _ = Profile.objects.get_or_create(user=user, defaults={'nickname': user.username})
            profile.previous_login = profile.current_login
            profile.current_login = timezone.now()
            profile.login_count += 1
            profile.save()
            return redirect('forum:index')
        request.session['login_error'] = '아이디 또는 비밀번호가 올바르지 않습니다.'
    return redirect('forum:index')


def logout_view(request):
    logout(request)
    return redirect('forum:index')


@login_required
def profile_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user, defaults={'nickname': request.user.username})

    from machina.apps.forum_conversation.models import Topic, Post
    topic_count = Topic.objects.filter(poster=request.user).count()
    post_count = Post.objects.filter(poster=request.user).count() - topic_count
    scrap_count = Topic.objects.filter(subscribers=request.user).count()

    context = {
        'profile': profile,
        'topic_count': topic_count,
        'post_count': post_count,
        'scrap_count': scrap_count,
    }
    return render(request, 'accounts/profile.html', context)


@login_required
def change_nickname(request):
    if request.method == 'POST':
        nickname = request.POST.get('nickname', '').strip()
        if not nickname:
            return redirect('profile')
        if Profile.objects.filter(nickname=nickname).exclude(user=request.user).exists():
            return redirect('profile')
        profile, _ = Profile.objects.get_or_create(user=request.user, defaults={'nickname': request.user.username})
        if profile.nickname == nickname:
            return redirect('profile')
        if profile.nickname_changed_at:
            from datetime import timedelta
            if timezone.now() - profile.nickname_changed_at < timedelta(days=15):
                return redirect('profile')
        profile.nickname = nickname
        profile.nickname_changed_at = timezone.now()
        profile.save()
    return redirect('profile')


@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, user)
    return redirect('profile')


@login_required
def my_topics(request):
    from machina.apps.forum_conversation.models import Topic
    topics = Topic.objects.filter(poster=request.user).order_by('-created')
    return render(request, 'accounts/my_topics.html', {'topics': topics})


@login_required
def my_replies(request):
    from machina.apps.forum_conversation.models import Post, Topic
    first_post_ids = Topic.objects.filter(poster=request.user).values_list('first_post_id', flat=True)
    replies = Post.objects.filter(poster=request.user).exclude(pk__in=first_post_ids).order_by('-created')
    return render(request, 'accounts/my_replies.html', {'replies': replies})


@login_required
def vote_topic(request, topic_id):
    if request.method == 'POST':
        from machina.apps.forum_conversation.models import Topic
        topic = Topic.objects.get(pk=topic_id)
        vote_type = int(request.POST.get('vote', 0))
        if vote_type not in (1, -1):
            return JsonResponse({'error': 'invalid'}, status=400)
        existing = TopicVote.objects.filter(user=request.user, topic=topic).first()
        if existing:
            if existing.vote == vote_type:
                existing.delete()
            else:
                existing.vote = vote_type
                existing.save()
        else:
            TopicVote.objects.create(user=request.user, topic=topic, vote=vote_type)
        up = TopicVote.objects.filter(topic=topic, vote=1).count()
        down = TopicVote.objects.filter(topic=topic, vote=-1).count()
        return JsonResponse({'up': up, 'down': down})
    return JsonResponse({'error': 'method'}, status=405)


@login_required
def reply_to_post(request, parent_id):
    """Create a 대댓글 (reply to a comment) reusing machina's PostForm."""
    from django.urls import reverse
    from machina.apps.forum_conversation.models import Post
    from machina.apps.forum_conversation.forms import PostForm

    parent = get_object_or_404(Post.objects.select_related('topic', 'topic__forum'), pk=parent_id)
    topic = parent.topic
    forum = topic.forum

    topic_url = reverse('forum_conversation:topic', kwargs={
        'forum_slug': forum.slug, 'forum_pk': forum.pk,
        'slug': topic.slug, 'pk': topic.pk,
    })

    # Replies cascade (A -> B -> C -> D) but nesting stops at MAX_REPLY_DEPTH.
    # A reply to a comment already at the deepest level becomes a sibling there
    # by hanging off that comment's own parent instead of nesting further.
    from accounts.templatetags.community_tags import MAX_REPLY_DEPTH
    parent_map = dict(
        PostReply.objects.filter(post__topic=topic).values_list('post_id', 'parent_id')
    )

    def depth_of(post_id):
        # 0-based: a top-level comment is depth 0.
        depth = 0
        seen = set()
        current = parent_map.get(post_id)
        while current and current not in seen:
            seen.add(current)
            depth += 1
            current = parent_map.get(current)
        return depth

    top_parent = parent
    if depth_of(parent.pk) >= MAX_REPLY_DEPTH - 1:
        # Parent is at the last allowed level; attach to its parent instead.
        grandparent_id = parent_map.get(parent.pk)
        if grandparent_id:
            top_parent = get_object_or_404(Post, pk=grandparent_id)

    if not request.forum_permission_handler.can_add_post(topic, request.user):
        return HttpResponseRedirect(topic_url)

    if request.method == 'POST':
        data = request.POST.copy()
        data['subject'] = 'Re: {}'.format(topic.subject)
        form = PostForm(data=data, user=request.user, forum=forum, topic=topic)
        if form.is_valid():
            post = form.save()
            PostReply.objects.create(post=post, parent=top_parent)
            return HttpResponseRedirect('{0}?post={1}#{1}'.format(topic_url, post.pk))
    return HttpResponseRedirect(topic_url)


@login_required
def delete_comment(request, post_id):
    """Delete a comment. If it still has replies, keep it as a tombstone so the
    replies stay nested beneath it; otherwise remove the post entirely."""
    from django.urls import reverse
    from machina.apps.forum_conversation.models import Post
    from .models import DeletedComment

    post = get_object_or_404(Post.objects.select_related('topic', 'topic__forum'), pk=post_id)
    topic = post.topic
    forum = topic.forum
    topic_url = reverse('forum_conversation:topic', kwargs={
        'forum_slug': forum.slug, 'forum_pk': forum.pk,
        'slug': topic.slug, 'pk': topic.pk,
    })

    if not request.forum_permission_handler.can_delete_post(post, request.user):
        return HttpResponseRedirect(topic_url)

    if request.method == 'POST':
        has_children = PostReply.objects.filter(parent=post).exists()
        if has_children:
            DeletedComment.objects.get_or_create(
                post=post, defaults={'deleted_by': request.user})
        else:
            post.delete()
    return HttpResponseRedirect(topic_url)


@login_required
def delete_account(request):
    if request.method == 'POST':
        user = request.user
        logout(request)
        user.delete()
    return redirect('forum:index')
