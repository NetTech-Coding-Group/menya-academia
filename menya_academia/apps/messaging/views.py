import json

from django.contrib import messages as django_messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.activity_logs.models import ActivityLog
from apps.courses.models import Course
from apps.notifications.services import notify_new_message

from .forms import MessageForm, SupportConversationForm
from .models import Conversation, Message
from .services import (
    can_access_conversation,
    can_send_in_conversation,
    conversations_for_user,
    enrolled_paid_courses_for_student,
    get_or_create_student_teacher_conversation,
    get_or_create_support_conversation,
    is_admin_user,
    is_approved_teacher,
    mark_conversation_read,
    student_can_use_messaging,
    student_can_message_teacher,
)


MESSAGES_PER_PAGE = 30


def _messaging_home_for(user):
    return reverse("messaging:inbox")


def _require_messaging_access(user):
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied("Authentication required.")
    role = getattr(user, "role", "")
    if role == user.Role.STUDENT:
        return
    if role == user.Role.TEACHER:
        if not is_approved_teacher(user):
            raise PermissionDenied("Your teacher account must be approved before using messaging.")
        return
    if is_admin_user(user):
        return
    raise PermissionDenied("Messaging is not available for this account.")


def _serialize_message(message, user):
    return {
        "id": str(message.id),
        "sender_id": str(message.sender_id),
        "sender_name": message.sender.full_name,
        "is_own": message.sender_id == user.id,
        "content": message.content,
        "created_at": timezone.localtime(message.created_at).strftime("%d %b %Y, %H:%M"),
        "is_read": message.is_read,
        "read_at": timezone.localtime(message.read_at).strftime("%d %b %Y, %H:%M") if message.read_at else None,
    }


def _conversation_display(conversation, user):
    other = conversation.other_party_for(user)
    if conversation.conversation_type == Conversation.Type.STUDENT_TEACHER:
        title = conversation.teacher.full_name if user.id == conversation.student_id else conversation.student.full_name
        subtitle = conversation.course.title if conversation.course_id else "Course"
    else:
        title = "Administration Support" if user.role == user.Role.STUDENT else conversation.student.full_name
        subtitle = conversation.get_category_display()
    return {
        "conversation": conversation,
        "title": title,
        "subtitle": subtitle,
        "other": other,
        "unread": getattr(conversation, "unread_count", 0),
    }


@login_required(login_url="accounts:login")
def inbox(request):
    _require_messaging_access(request.user)
    conversations = list(conversations_for_user(request.user))
    items = [_conversation_display(c, request.user) for c in conversations]

    enrolled_courses = []
    if student_can_use_messaging(request.user):
        enrolled_courses = list(enrolled_paid_courses_for_student(request.user))

    context = {
        "conversation_items": items,
        "enrolled_courses": enrolled_courses,
        "is_student": student_can_use_messaging(request.user),
        "is_teacher": is_approved_teacher(request.user),
        "is_admin_messaging": is_admin_user(request.user),
        "support_form": SupportConversationForm() if student_can_use_messaging(request.user) else None,
    }
    return render(request, "messaging/inbox.html", context)


@login_required(login_url="accounts:login")
@require_POST
def start_teacher_conversation(request, teacher_id):
    if not student_can_use_messaging(request.user):
        raise PermissionDenied("Only students can start teacher conversations.")

    course_id = request.POST.get("course_id") or request.GET.get("course_id")
    if not course_id:
        django_messages.error(request, "Please select a course for this conversation.")
        return redirect("messaging:inbox")

    course = get_object_or_404(Course, pk=course_id, is_archived=False)
    teacher = course.teacher
    if str(teacher.pk) != str(teacher_id):
        # Don't trust client-provided teacher_id over course ownership.
        raise PermissionDenied("Invalid teacher for the selected course.")

    if not student_can_message_teacher(request.user, teacher, course):
        raise PermissionDenied("You can only message the teacher responsible for your enrolled course.")

    conversation = get_or_create_student_teacher_conversation(
        student=request.user,
        teacher=teacher,
        course=course,
    )
    return redirect("messaging:conversation_detail", conversation_id=conversation.pk)


@login_required(login_url="accounts:login")
def contact_admin(request):
    if not student_can_use_messaging(request.user):
        raise PermissionDenied("Only students can contact administration.")

    if request.method == "POST":
        form = SupportConversationForm(request.POST)
        if form.is_valid():
            conversation = get_or_create_support_conversation(
                student=request.user,
                category=form.cleaned_data["category"],
                subject=form.cleaned_data["subject"],
            )
            msg = Message.objects.create(
                conversation=conversation,
                sender=request.user,
                content=form.cleaned_data["content"],
            )
            conversation.touch()
            if conversation.status == Conversation.Status.RESOLVED:
                conversation.status = Conversation.Status.OPEN
                conversation.save(update_fields=["status", "updated_at"])
            notify_new_message(message_obj=msg)
            ActivityLog.objects.create(
                actor=request.user,
                actor_name=request.user.full_name,
                actor_email=request.user.email,
                actor_role=request.user.role,
                action="messaging.support_message_sent",
                description=f"Sent support message in category {conversation.get_category_display()}.",
            )
            django_messages.success(request, "Your message has been sent to the administration.")
            return redirect("messaging:conversation_detail", conversation_id=conversation.pk)
    else:
        form = SupportConversationForm()

    return render(request, "messaging/contact_admin.html", {"form": form})


@login_required(login_url="accounts:login")
def conversation_detail(request, conversation_id):
    _require_messaging_access(request.user)
    conversation = get_object_or_404(
        Conversation.objects.select_related("student", "teacher", "course"),
        pk=conversation_id,
    )
    if not can_access_conversation(request.user, conversation):
        raise PermissionDenied("You do not have access to this conversation.")

    mark_conversation_read(conversation, request.user)

    qs = conversation.messages.select_related("sender").order_by("created_at")
    paginator = Paginator(qs, MESSAGES_PER_PAGE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number or paginator.num_pages)
    chat_messages = list(page_obj.object_list)
    last_message_id = chat_messages[-1].pk if chat_messages else ""

    conversations = list(conversations_for_user(request.user))
    items = [_conversation_display(c, request.user) for c in conversations]

    context = {
        "conversation": conversation,
        "conversation_items": items,
        "page_obj": page_obj,
        "chat_messages": chat_messages,
        "last_message_id": last_message_id,
        "message_form": MessageForm(),
        "can_send": can_send_in_conversation(request.user, conversation),
        "is_admin_messaging": is_admin_user(request.user),
        "is_student": student_can_use_messaging(request.user),
        "is_teacher": is_approved_teacher(request.user),
        "status_choices": Conversation.Status.choices,
    }
    return render(request, "messaging/conversation_detail.html", context)


@login_required(login_url="accounts:login")
@require_POST
def send_message(request, conversation_id):
    _require_messaging_access(request.user)
    conversation = get_object_or_404(
        Conversation.objects.select_related("student", "teacher", "course"),
        pk=conversation_id,
    )
    if not can_send_in_conversation(request.user, conversation):
        return JsonResponse({"ok": False, "error": "You do not have permission to send messages in this conversation."}, status=403)

    form = MessageForm(request.POST)
    if not form.is_valid():
        error = "; ".join(form.errors.get("content", ["Invalid message."]))
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": error}, status=400)
        django_messages.error(request, error)
        return redirect("messaging:conversation_detail", conversation_id=conversation.pk)

    with transaction.atomic():
        msg = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            content=form.cleaned_data["content"],
        )
        conversation.last_message_at = msg.created_at
        update_fields = ["last_message_at", "updated_at"]
        if conversation.conversation_type == Conversation.Type.STUDENT_ADMIN:
            # Reopen resolved support conversations when a new message arrives.
            if conversation.status == Conversation.Status.RESOLVED:
                conversation.status = Conversation.Status.OPEN
                update_fields.append("status")
        conversation.save(update_fields=update_fields)

    notify_new_message(message_obj=msg)
    ActivityLog.objects.create(
        actor=request.user,
        actor_name=request.user.full_name,
        actor_email=request.user.email,
        actor_role=request.user.role,
        action="messaging.message_sent",
        description=f"Sent a message in conversation {conversation.pk}.",
    )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "message": _serialize_message(msg, request.user)})

    return redirect("messaging:conversation_detail", conversation_id=conversation.pk)


@login_required(login_url="accounts:login")
@require_GET
def conversation_messages(request, conversation_id):
    _require_messaging_access(request.user)
    conversation = get_object_or_404(Conversation, pk=conversation_id)
    if not can_access_conversation(request.user, conversation):
        return JsonResponse({"ok": False, "error": "Forbidden"}, status=403)

    after = request.GET.get("after")
    qs = conversation.messages.select_related("sender").order_by("created_at")
    if after:
        try:
            # after is a message UUID; include messages created after that message's created_at
            anchor = conversation.messages.filter(pk=after).first()
            if anchor:
                qs = qs.filter(created_at__gt=anchor.created_at)
        except Exception:
            pass

    # Mark incoming as read on poll/fetch, as user is viewing conversation.
    mark_conversation_read(conversation, request.user)
    messages_data = [_serialize_message(m, request.user) for m in qs]
    # also update read status for returned messages that belong to sender? not necessary
    return JsonResponse(
        {
            "ok": True,
            "messages": messages_data,
            "conversation_status": conversation.status,
            "conversation_status_display": conversation.get_status_display(),
        }
    )


@login_required(login_url="accounts:login")
@require_POST
def update_support_status(request, conversation_id):
    if not is_admin_user(request.user):
        raise PermissionDenied("Only administrators can update support status.")
    conversation = get_object_or_404(
        Conversation,
        pk=conversation_id,
        conversation_type=Conversation.Type.STUDENT_ADMIN,
    )
    status = request.POST.get("status")
    valid = {s for s, _ in Conversation.Status.choices}
    if status not in valid:
        django_messages.error(request, "Invalid status.")
        return redirect("messaging:conversation_detail", conversation_id=conversation.pk)
    conversation.status = status
    conversation.save(update_fields=["status", "updated_at"])
    ActivityLog.objects.create(
        actor=request.user,
        actor_name=request.user.full_name,
        actor_email=request.user.email,
        actor_role=request.user.role,
        action="messaging.support_status_updated",
        description=f"Updated support conversation {conversation.pk} status to {conversation.get_status_display()}.",
    )
    django_messages.success(request, "Conversation status updated.")
    return redirect("messaging:conversation_detail", conversation_id=conversation.pk)
