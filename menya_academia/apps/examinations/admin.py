from django.contrib import admin

from .models import AnswerOption, AttemptAnswer, AttemptQuestion, ExamAttempt, Question


class AnswerOptionInline(admin.TabularInline):
    model = AnswerOption
    extra = 4
    max_num = 4


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "short_text_rw", "approval_status", "is_active", "created_at")
    list_filter = ("approval_status", "is_active")
    search_fields = ("text_en", "text_fr", "text_rw")
    list_editable = ("approval_status", "is_active")
    inlines = (AnswerOptionInline,)
    actions = ("approve_questions",)

    @admin.display(description="Question (Kinyarwanda)")
    def short_text_rw(self, obj):
        text = (obj.text_rw or obj.text_en or obj.text_fr or "").strip()
        return text[:80]

    @admin.action(description="Approve selected questions")
    def approve_questions(self, request, queryset):
        updated = queryset.update(
            approval_status=Question.ApprovalStatus.APPROVED,
            is_active=True,
        )
        self.message_user(request, f"{updated} question(s) approved.")


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
