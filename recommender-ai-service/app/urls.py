from django.urls import path
from . import views

urlpatterns = [
    # ── Recommendations ──────────────────────────────────────
    path('recommendations/',                views.recommendations_list,  name='recommendations'),
    path('recommendations/track/',          views.track_interaction,     name='track'),
    path('recommendations/behavior/',       views.behavior_profile,      name='behavior'),
    path('recommendations/popular/',        views.popular_books,         name='popular'),

    # ── Chatbot ───────────────────────────────────────────────
    path('ai/chat/',                        views.chat,                  name='chat'),
    path('ai/chat/history/',               views.chat_history,          name='chat_history'),

    # ── Knowledge Base ────────────────────────────────────────
    path('ai/kb/',                          views.kb_list,               name='kb_list'),
    path('ai/kb/seed/',                     views.kb_seed,               name='kb_seed'),
    path('ai/kb/ingest_books/',             views.kb_ingest_books,       name='kb_ingest'),
    path('ai/kb/search/',                   views.kb_search,             name='kb_search'),

    # ── Health ────────────────────────────────────────────────
    path('ai/health/',                      views.health,                name='ai_health'),
]
