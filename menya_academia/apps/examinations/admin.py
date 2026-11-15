from django.contrib import admin

from .models import AnswerOption, AttemptAnswer, AttemptQuestion, ExamAttempt, Question


class AnswerOptionInline(admin.TabularInline):
    model = AnswerOption
    extra = 4
    max_num = 4


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "text_en", "text_rw", "is_active")
    list_filter = ("is_active",)
    search_fields = ("text_en", "text_fr", "text_rw")
    inlines = (AnswerOptionInline,)


class AttemptQuestionInline(admin.TabularInline):
    model = AttemptQuestion
    extra = 0
    readonly_fields = ("question", "correct_option", "position")
    can_delete = False


class AttemptAnswerInline(admin.TabularInline):
    model = AttemptAnswer
    extra = 0
    readonly_fields = ("question", "selected_option", "is_correct", "updated_at")
    can_delete = False


@admin.register(ExamAttempt)
class ExamAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "anonymous_id",
        "exam",
        "status",
        "score_percentage",
        "passed",
        "started_at",
    )
    list_filter = ("status", "passed", "exam")
    search_fields = ("anonymous_id",)
    readonly_fields = (
        "user",
        "activation_code",
        "anonymous_id",
        "status",
        "total_questions",
        "pass_mark",
        "score_percentage",
        "correct_answers",
        "passed",
        "started_at",
        "deadline",
        "completed_at",
    )
    inlines = (AttemptQuestionInline, AttemptAnswerInline)
