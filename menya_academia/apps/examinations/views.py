from django import forms
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.templatetags.ui_translations import translate_ui
from apps.activation_codes.services import CodeActivationError
from apps.examinations.models import AttemptAnswer, AttemptQuestion, ExamAttempt
from apps.examinations.services import (
    ExamAccessError,
    ExamUnavailable,
    save_answer,
    start_exam_for_code,
    submit_attempt,
)


class ActivationForm(forms.Form):
    code = forms.CharField(max_length=40, label="Activation code")


def home(request):
    return render(request, "public/home.html")


def activate(request):
    form = ActivationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            attempt = start_exam_for_code(
                code_text=form.cleaned_data["code"],
                user=request.user if request.user.is_authenticated else None,
            )
        except (CodeActivationError, ExamAccessError, ExamUnavailable) as exc:
            form.add_error("code", translate_ui(str(exc), request.LANGUAGE_CODE))
        else:
            if not attempt.user_id:
                attempt_ids = set(request.session.get("exam_attempt_ids", []))
                attempt_ids.add(str(attempt.pk))
                request.session["exam_attempt_ids"] = sorted(attempt_ids)
            return redirect("exam_take", attempt_id=attempt.pk)
    return render(request, "provisual/activate.html", {"form": form})


def _can_access_attempt(attempt, request):
    if attempt.user_id:
        return request.user.is_authenticated and request.user.pk == attempt.user_id
    return str(attempt.pk) in request.session.get("exam_attempt_ids", [])


def save_exam_answer(request, attempt_id):
    if request.method != "POST":
        return JsonResponse(
            {"error": translate_ui("POST is required.", request.LANGUAGE_CODE)},
            status=405,
        )
    attempt = get_object_or_404(ExamAttempt, pk=attempt_id)
    if not _can_access_attempt(attempt, request):
        raise Http404
    if not request.POST.get("option"):
        return JsonResponse(
            {"error": translate_ui("Select an answer first.", request.LANGUAGE_CODE)},
            status=400,
        )
    try:
        saved = save_answer(
            attempt_id=attempt.pk,
            question_id=request.POST.get("question_id"),
            option_id=request.POST.get("option"),
            user=request.user,
        )
    except ExamAccessError as exc:
        return JsonResponse(
            {"error": translate_ui(str(exc), request.LANGUAGE_CODE)},
            status=400,
        )
    if not saved:
        return JsonResponse(
            {
                "error": translate_ui(
                    "The examination time has ended.", request.LANGUAGE_CODE
                )
            },
            status=409,
        )
    return JsonResponse({"saved": True})


def take_exam(request, attempt_id):
    attempt = get_object_or_404(ExamAttempt, pk=attempt_id)
    if not _can_access_attempt(attempt, request):
        raise Http404
    if attempt.status != ExamAttempt.Status.IN_PROGRESS:
        return redirect("exam_results", attempt_id=attempt.pk)
    if timezone.now() >= attempt.deadline:
        attempt = submit_attempt(attempt_id=attempt.pk, user=request.user)
        return redirect("exam_results", attempt_id=attempt.pk)

    entries = list(
        AttemptQuestion.objects.filter(attempt=attempt)
        .select_related("question")
        .prefetch_related("question__options")
    )
    if not entries:
        raise Http404("No questions were assigned to this attempt.")
    try:
        position = int(request.GET.get("q", "1"))
    except ValueError:
        position = 1
    position = min(max(position, 1), len(entries))
    entry = entries[position - 1]

    if request.method == "POST":
        try:
            answer_saved = save_answer(
                attempt_id=attempt.pk,
                question_id=entry.question_id,
                option_id=request.POST.get("option") or None,
                user=request.user,
            )
        except (ExamAccessError, AttemptQuestion.DoesNotExist):
            raise Http404
        if not answer_saved:
            return redirect("exam_results", attempt_id=attempt.pk)
        if request.POST.get("finish") == "1":
            submit_attempt(attempt_id=attempt.pk, user=request.user)
            return redirect("exam_results", attempt_id=attempt.pk)
        if request.POST.get("move") == "previous":
            position = max(1, position - 1)
        else:
            position = min(len(entries), position + 1)
        return redirect(f"{request.path}?q={position}")

    previous_answer = AttemptAnswer.objects.filter(
        attempt=attempt, question=entry.question
    ).first()
    language = request.LANGUAGE_CODE
    options = [
        (option, option.get_text(language)) for option in entry.question.options.all()
    ]
    return render(
        request,
        "provisual/exam_take.html",
        {
            "attempt": attempt,
            "entry": entry,
            "question_text": entry.question.get_text(language),
            "options": options,
            "position": position,
            "question_count": len(entries),
            "selected_option_id": previous_answer.selected_option_id
            if previous_answer
            else None,
        },
    )


def submit_exam(request, attempt_id):
    if request.method != "POST":
        raise Http404
    attempt = get_object_or_404(ExamAttempt, pk=attempt_id)
    if not _can_access_attempt(attempt, request):
        raise Http404
    try:
        submit_attempt(attempt_id=attempt.pk, user=request.user)
    except ExamAccessError:
        raise Http404
    return redirect("exam_results", attempt_id=attempt.pk)


def _visible_attempt(attempt_id, request):
    attempt = get_object_or_404(ExamAttempt, pk=attempt_id)
    if not _can_access_attempt(attempt, request):
        raise Http404
    if attempt.status == ExamAttempt.Status.IN_PROGRESS:
        raise Http404
    return attempt


def exam_results(request, attempt_id):
    attempt = _visible_attempt(attempt_id, request)
    return render(
        request,
        "provisual/exam_results.html",
        {
            "attempt": attempt,
            "incorrect_answers": attempt.total_questions - attempt.correct_answers,
        },
    )


def exam_review(request, attempt_id):
    attempt = _visible_attempt(attempt_id, request)
    questions = (
        AttemptQuestion.objects.filter(attempt=attempt)
        .select_related("question")
        .prefetch_related("question__options")
    )
    answers = {
        answer.question_id: answer
        for answer in AttemptAnswer.objects.filter(attempt=attempt).select_related(
            "selected_option"
        )
    }
    language = request.LANGUAGE_CODE
    review_rows = []
    for entry in questions:
        answer = answers.get(entry.question_id)
        review_rows.append(
            {
                "entry": entry,
                "answer": answer,
                "text": entry.question.get_text(language),
                "explanation": entry.question.get_explanation(language),
                "options": [
                    (option, option.get_text(language))
                    for option in entry.question.options.all()
                ],
            }
        )
    return render(
        request,
        "provisual/exam_review.html",
        {"attempt": attempt, "review_rows": review_rows},
    )


def community_results(request):
    attempts = (
        ExamAttempt.objects.filter(
            status__in=(ExamAttempt.Status.COMPLETED, ExamAttempt.Status.TIMED_OUT)
        )
        .order_by("-completed_at")[:50]
    )
    return render(
        request,
        "provisual/community_results.html",
        {"attempts": attempts},
    )
