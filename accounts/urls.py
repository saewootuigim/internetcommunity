from django.urls import path

from . import views

urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('nickname/', views.change_nickname, name='change_nickname'),
    path('password/', views.change_password, name='change_password'),
    path('my-topics/', views.my_topics, name='my_topics'),
    path('my-replies/', views.my_replies, name='my_replies'),
    path('delete/', views.delete_account, name='delete_account'),
    path('vote/<int:topic_id>/', views.vote_topic, name='vote_topic'),
    path('reply/<int:parent_id>/', views.reply_to_post, name='reply_to_post'),
    path('comment/<int:post_id>/delete/', views.delete_comment, name='delete_comment'),
]
