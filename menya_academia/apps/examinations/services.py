import random
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.activation_codes.models import ActivationCode
from apps.activation_codes.services import activate_code
from apps.examinations.models import (
    AnswerOption,
    AttemptAnswer,
    AttemptQuestion,
    ExamAttempt,
    Question,
)
from apps.provisual.models import Exam


class ExamUnavailable(Exception):
    pass


class ExamAccessError(Exception):
    pass


@transaction.atomic
def start_exam_for_code(*, code_text, user=None):
    try:
        exam = Exam.objects.get(slug="practice", is_active=True)
    except Exam.DoesNotExist as exc:
        raise ExamUnavailable("The practice examination is not configured.") from exc

    approved_filter = {
        "is_active": True,
        "approval_status": Question.ApprovalStatus.APPROVED,
    }
    selected_pool = (
        exam.selected_questions.filter(**approved_filter) if exam.pk else Question.objects.none()
    )
    question_qs = (
        selected_pool if selected_pool.exists() else Question.objects.filter(**approved_filter)
    )
    eligible_questions = []
    for question in question_qs.prefetch_related("options"):
        options = list(question.options.all())
        if len(options) == 4 and sum(option.is_correct for option in options) == 1:
            correct_option = next(option for option in options if option.is_correct)
            eligible_questions.append((question, correct_option))
    if len(eligible_questions) < exam.question_count:
        raise ExamUnavailable(
            f"The question bank needs {exam.question_count} complete questions; "
            f"only {len(eligible_questions)} are ready."
        )

    activation_code = activate_code(code_text=code_text, user=user)
    existing_attempt = (
        ExamAttempt.objects.select_for_update()
        .filter(
            activation_code=activation_code,
            status=ExamAttempt.Status.IN_PROGRESS,
        )
        .first()
    )
    if existing_attempt:
        return existing_attempt

    if (
        activation_code.package.max_exam_attempts
        and activation_code.attempts_made >= activation_code.package.max_exam_attempts
    ):
        raise ExamAccessError("The examination limit for this code has been reached.")

    selected_questions = random.SystemRandom().sample(
        eligible_questions, exam.question_count
    )
    now = timezone.now()
    attempt = ExamAttempt.objects.create(
        exam=exam,
        user=user if user and user.is_authenticated else None,
        activation_code=activation_code,
        total_questions=len(selected_questions),
        pass_mark=exam.pass_mark,
        deadline=now + timedelta(minutes=exam.duration_minutes),
    )
    AttemptQuestion.objects.bulk_create(
        [
            AttemptQuestion(
                attempt=attempt,
                question=question,
                correct_option=correct_option,
                position=position,
            )
            for position, (question, correct_option) in enumerate(
                selected_questions, start=1
            )
        ]
    )
    return attempt


@transaction.atomic
def save_answer(*, attempt_id, question_id, option_id, user=None):
    attempt = ExamAttempt.objects.select_for_update().get(pk=attempt_id)
    if attempt.status != ExamAttempt.Status.IN_PROGRESS:
        raise ExamAccessError("This examination has already been submitted.")
    if attempt.user_id and user and user.is_authenticated and attempt.user_id != user.pk:
        raise ExamAccessError("This examination belongs to another account.")
    if timezone.now() >= attempt.deadline:
        submit_attempt(attempt_id=attempt.pk, user=user)
        return False

    try:
        question_entry = AttemptQuestion.objects.get(
            attempt=attempt, question_id=question_id
        )
    except (AttemptQuestion.DoesNotExist, TypeError, ValueError) as exc:
        raise ExamAccessError("This question is not part of the examination.") from exc
    if not option_id:
        return True
    try:
        option = AnswerOption.objects.get(pk=option_id, question=question_entry.question)
    except (AnswerOption.DoesNotExist, TypeError, ValueError) as exc:
        raise ExamAccessError("Choose one of the answers for this question.") from exc
    AttemptAnswer.objects.update_or_create(
        attempt=attempt,
        question=question_entry.question,
        defaults={"selected_option": option, "is_correct": False},
    )
    return True


@transaction.atomic
def submit_attempt(*, attempt_id, user=None):
    attempt = ExamAttempt.objects.select_for_update().get(pk=attempt_id)
    if attempt.user_id and user and user.is_authenticated and attempt.user_id != user.pk:
        raise ExamAccessError("This examination belongs to another account.")
    if attempt.status != ExamAttempt.Status.IN_PROGRESS:
        return attempt

    correct_count = 0
    correct_options = {
        entry.question_id: entry.correct_option_id
        for entry in attempt.ordered_questions.all()
    }
    answer_rows = list(
        attempt.recorded_answers.select_related("selected_option").all()
    )
    for answer in answer_rows:
        answer.is_correct = answer.selected_option_id == correct_options.get(
            answer.question_id
        )
        if answer.is_correct:
            correct_count += 1
    if answer_rows:
        AttemptAnswer.objects.bulk_update(answer_rows, ("is_correct",))

    percentage = (
        Decimal(correct_count * 100) / Decimal(attempt.total_questions)
    ).quantize(Decimal("0.01"))
    timed_out = timezone.now() >= attempt.deadline
    attempt.correct_answers = correct_count
    attempt.score_percentage = percentage
    attempt.passed = percentage >= attempt.pass_mark
    attempt.status = (
        ExamAttempt.Status.TIMED_OUT if timed_out else ExamAttempt.Status.COMPLETED
    )
    attempt.completed_at = timezone.now()
    attempt.save(
        update_fields=(
            "correct_answers",
            "score_percentage",
            "passed",
            "status",
            "completed_at",
        )
    )

    code = attempt.activation_code
    code.attempts_made += 1
    if (
        code.package.max_exam_attempts
        and code.attempts_made >= code.package.max_exam_attempts
    ):
        code.status = ActivationCode.Status.CONSUMED
    code.save(update_fields=("attempts_made", "status"))
    return attempt
