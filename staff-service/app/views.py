import requests
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from .models import ActivityLog, PermissionType, Role, Shift, ShiftStatus, Staff
from .serializers import ActivityLogSerializer, ShiftSerializer, StaffCreateSerializer, StaffSerializer


ROLE_PERMISSIONS = {
    Role.ADMIN: set(PermissionType.values),
    Role.MANAGER: {
        PermissionType.VIEW_DASHBOARD,
        PermissionType.VIEW_ANALYTICS,
        PermissionType.VIEW_AUDIT_LOG,
        PermissionType.MANAGE_BOOKS,
        PermissionType.MANAGE_INVENTORY,
        PermissionType.MANAGE_ORDERS,
        PermissionType.UPDATE_ORDER_STATUS,
        PermissionType.MANAGE_PAYMENTS,
        PermissionType.PROCESS_REFUNDS,
        PermissionType.MANAGE_SHIPMENTS,
        PermissionType.MANAGE_CUSTOMERS,
        PermissionType.MANAGE_STAFF,
        PermissionType.MANAGE_SHIFTS,
        PermissionType.VIEW_SHIFTS,
        PermissionType.MANAGE_ROLES,
    },
    Role.INVENTORY: {
        PermissionType.VIEW_DASHBOARD,
        PermissionType.MANAGE_BOOKS,
        PermissionType.MANAGE_INVENTORY,
        PermissionType.VIEW_AUDIT_LOG,
    },
    Role.SHIPPING: {
        PermissionType.VIEW_DASHBOARD,
        PermissionType.MANAGE_SHIPMENTS,
        PermissionType.UPDATE_ORDER_STATUS,
        PermissionType.VIEW_SHIFTS,
        PermissionType.MANAGE_SHIFTS,
        PermissionType.VIEW_AUDIT_LOG,
    },
    Role.STAFF: {
        PermissionType.VIEW_DASHBOARD,
        PermissionType.VIEW_SHIFTS,
    },
}


def _permissions_for_role(role):
    return ROLE_PERMISSIONS.get(role, set())


def _has_permission(staff, perm):
    return perm in _permissions_for_role(staff.role)


def _log(actor, action, *, resource_type="", resource_id="", message="", meta=None):
    try:
        ActivityLog.objects.create(
            actor=actor,
            action=action,
            resource_type=resource_type or "",
            resource_id=str(resource_id) if resource_id else "",
            message=message or "",
            meta=meta,
        )
    except Exception:
        # Audit logging should never break the request.
        pass


def _gateway_role(request):
    role = (
        request.headers.get('X-User-Role')
        or request.META.get('HTTP_X_USER_ROLE')
        or request.META.get('X_USER_ROLE')
        or ''
    )
    return role.strip().lower()


def _gateway_can_manage_staff(request):
    return _gateway_role(request) in (Role.ADMIN, Role.MANAGER)


class StaffViewSet(viewsets.ModelViewSet):
    """Staff Service - Staff management and operations"""
    queryset = Staff.objects.all()
    serializer_class = StaffSerializer
    
    def get_serializer_class(self):
        if self.action == 'create':
            return StaffCreateSerializer
        return StaffSerializer

    @action(detail=False, methods=['post'])
    def login(self, request):
        """Staff login"""
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not username or not password:
            return Response({'error': 'Username and password required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            staff = Staff.objects.get(username=username)
            if staff.check_password(password):
                token, created = Token.objects.get_or_create(user=staff)
                _log(staff, "login", resource_type="staff", resource_id=staff.id, message="staff login")
                return Response({
                    'message': 'Login successful',
                    'token': token.key,
                    'staff': StaffSerializer(staff).data
                }, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        except Staff.DoesNotExist:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

    @action(detail=False, methods=['get'])
    def roles(self, request):
        """List roles and their permissions (static mapping)"""
        return Response(
            {"roles": [{"role": role, "permissions": sorted(list(_permissions_for_role(role)))} for role in Role.values]},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=['get'])
    def permissions(self, request):
        """List all permission types"""
        return Response({"permissions": list(PermissionType.values)}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def create_staff(self, request):
        """Create new staff member (admin/manager only)"""
        requester_id = request.data.get('requester_id')
        username = request.data.get('username')
        password = request.data.get('password')
        email = request.data.get('email')
        role = request.data.get('role', Role.STAFF)
        department = request.data.get('department', '')

        if not username or not password or not email:
            return Response({'error': 'username, email and password are required'}, status=status.HTTP_400_BAD_REQUEST)

        requester = None
        gw_role = _gateway_role(request)

        # Preferred path: trust JWT role forwarded by API Gateway.
        if gw_role in (Role.ADMIN, Role.MANAGER):
            pass
        else:
            if not requester_id:
                return Response({'error': 'requester_id is required'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                requester = Staff.objects.get(id=requester_id)
                if not _has_permission(requester, PermissionType.MANAGE_STAFF):
                    return Response({'error': 'You do not have permission to create staff'}, status=status.HTTP_403_FORBIDDEN)
            except Staff.DoesNotExist:
                return Response({'error': 'Requester not found'}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            staff = Staff.objects.create_user(
                username=username,
                password=password,
                email=email,
                role=role,
                department=department
            )
            _log(
                requester,
                "create_staff",
                resource_type="staff",
                resource_id=staff.id,
                meta={
                    "role": role,
                    "gateway_role": gw_role,
                    "requester_id": requester_id,
                },
            )
            return Response({
                'message': 'Staff created successfully',
                'staff': StaffSerializer(staff).data
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def by_role(self, request):
        """Get staff by role"""
        role = request.query_params.get('role')
        if not role:
            return Response({'error': 'role parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        staff_list = Staff.objects.filter(role=role)
        serializer = self.get_serializer(staff_list, many=True)
        
        return Response({
            'role': role,
            'count': len(staff_list),
            'staff': serializer.data
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def by_department(self, request):
        """Get staff by department"""
        department = request.query_params.get('department')
        if not department:
            return Response({'error': 'department parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        staff_list = Staff.objects.filter(department=department)
        serializer = self.get_serializer(staff_list, many=True)
        
        return Response({
            'department': department,
            'count': len(staff_list),
            'staff': serializer.data
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def manage_books(self, request):
        """Staff can manage books with role check"""
        staff_id = request.data.get('staff_id')
        operation = request.data.get('operation')  # create, update, delete, list
        book_data = request.data.get('book_data', {})
        book_id = request.data.get('book_id')
        
        if not staff_id or not operation:
            return Response({'error': 'staff_id and operation are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            staff = Staff.objects.get(id=staff_id)
        except Staff.DoesNotExist:
            return Response({'error': 'Staff not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check permission - only manager and admin can manage books
        if not _has_permission(staff, PermissionType.MANAGE_BOOKS):
            return Response({'error': 'You do not have permission to manage books'}, status=status.HTTP_403_FORBIDDEN)
        
        # Call Book Service to perform operation
        try:
            if operation == 'create':
                response = requests.post('http://book-service:8000/api/books/', json=book_data)
            elif operation == 'update':
                if not book_id:
                    return Response({'error': 'book_id is required for update'}, status=status.HTTP_400_BAD_REQUEST)
                response = requests.patch(f'http://book-service:8000/api/books/{book_id}/', json=book_data)
            elif operation == 'delete':
                if not book_id:
                    return Response({'error': 'book_id is required for delete'}, status=status.HTTP_400_BAD_REQUEST)
                response = requests.delete(f'http://book-service:8000/api/books/{book_id}/')
            elif operation == 'list':
                response = requests.get('http://book-service:8000/api/books/')
            else:
                return Response({'error': 'Invalid operation'}, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                payload = response.json()
            except Exception:
                payload = {"text": response.text}

            _log(
                staff,
                f"manage_books:{operation}",
                resource_type="book",
                resource_id=book_id or "",
                meta={"status_code": response.status_code},
            )
            return Response({
                'operation': operation,
                'result': payload
            }, status=response.status_code)
         
        except requests.exceptions.RequestException as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    @action(detail=True, methods=['patch'])
    def update_profile(self, request, pk=None):
        """Update staff profile"""
        staff = self.get_object()
        serializer = self.get_serializer(staff, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            _log(staff, "update_profile", resource_type="staff", resource_id=staff.id)
            return Response({
                'message': 'Profile updated successfully',
                'staff': serializer.data
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def active_staff(self, request):
        """Get all active staff members"""
        staff_list = Staff.objects.filter(is_active=True)
        serializer = self.get_serializer(staff_list, many=True)
        
        return Response({
            'count': len(staff_list),
            'staff': serializer.data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def check_permission(self, request, pk=None):
        """Check permissions for a staff member"""
        staff = self.get_object()
        
        return Response({
            'staff_id': staff.id,
            'username': staff.username,
            'role': staff.role,
            'permissions': sorted(list(_permissions_for_role(staff.role))),
            'can_manage_books': _has_permission(staff, PermissionType.MANAGE_BOOKS),
            'can_manage_staff': _has_permission(staff, PermissionType.MANAGE_STAFF),
            'is_admin': staff.is_admin(),
            'is_manager': staff.is_manager(),
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def has_permission(self, request):
        """Check a single permission for a staff member"""
        staff_id = request.data.get('staff_id')
        permission = request.data.get('permission')
        if not staff_id or not permission:
            return Response({'error': 'staff_id and permission are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            staff = Staff.objects.get(id=staff_id)
        except Staff.DoesNotExist:
            return Response({'error': 'Staff not found'}, status=status.HTTP_404_NOT_FOUND)

        allowed = permission in _permissions_for_role(staff.role)
        return Response({'staff_id': staff.id, 'permission': permission, 'allowed': allowed}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def activity_logs(self, request):
        """Get audit logs (manager/admin recommended)"""
        requester_id = request.query_params.get('requester_id')
        gw_manage = _gateway_can_manage_staff(request)
        if not requester_id and not gw_manage:
            return Response({'error': 'requester_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        requester = None
        if requester_id:
            try:
                requester = Staff.objects.get(id=requester_id)
            except Staff.DoesNotExist:
                if not gw_manage:
                    return Response({'error': 'Requester not found'}, status=status.HTTP_404_NOT_FOUND)

        if not gw_manage and not _has_permission(requester, PermissionType.VIEW_AUDIT_LOG):
            return Response({'error': 'You do not have permission to view audit logs'}, status=status.HTTP_403_FORBIDDEN)

        limit = int(request.query_params.get('limit', 50))
        actor_id = request.query_params.get('actor_id')

        logs = ActivityLog.objects.all()
        if actor_id:
            logs = logs.filter(actor_id=actor_id)
        logs = logs.order_by('-created_at')[:limit]

        return Response({'count': logs.count(), 'logs': ActivityLogSerializer(logs, many=True).data})

    @action(detail=False, methods=['post'])
    def create_shift(self, request):
        """Create/schedule a shift (requires manage_shifts)"""
        requester_id = request.data.get('requester_id')
        gw_manage = _gateway_can_manage_staff(request)
        if not requester_id and not gw_manage:
            return Response({'error': 'requester_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        requester = None
        if requester_id:
            try:
                requester = Staff.objects.get(id=requester_id)
            except Staff.DoesNotExist:
                if not gw_manage:
                    return Response({'error': 'Requester not found'}, status=status.HTTP_404_NOT_FOUND)

        if not gw_manage and not _has_permission(requester, PermissionType.MANAGE_SHIFTS):
            return Response({'error': 'You do not have permission to manage shifts'}, status=status.HTTP_403_FORBIDDEN)

        serializer = ShiftSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        shift = serializer.save(status=ShiftStatus.SCHEDULED)
        _log(requester, "create_shift", resource_type="shift", resource_id=shift.id, meta={"staff_id": shift.staff_id})
        return Response({'message': 'Shift created', 'shift': ShiftSerializer(shift).data}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def start_shift(self, request):
        """Start a shift (staff owns their shift)"""
        staff_id = request.data.get('staff_id')
        shift_id = request.data.get('shift_id')
        if not staff_id or not shift_id:
            return Response({'error': 'staff_id and shift_id are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            staff = Staff.objects.get(id=staff_id)
            shift = Shift.objects.get(id=shift_id, staff_id=staff_id)
        except Staff.DoesNotExist:
            return Response({'error': 'Staff not found'}, status=status.HTTP_404_NOT_FOUND)
        except Shift.DoesNotExist:
            return Response({'error': 'Shift not found'}, status=status.HTTP_404_NOT_FOUND)

        shift.status = ShiftStatus.STARTED
        shift.save(update_fields=['status'])
        _log(staff, "start_shift", resource_type="shift", resource_id=shift.id)
        return Response({'message': 'Shift started', 'shift': ShiftSerializer(shift).data}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def end_shift(self, request):
        """End a shift (staff owns their shift)"""
        staff_id = request.data.get('staff_id')
        shift_id = request.data.get('shift_id')
        if not staff_id or not shift_id:
            return Response({'error': 'staff_id and shift_id are required'}, status=status.HTTP_400_BAD_REQUEST)

        from django.utils import timezone

        try:
            staff = Staff.objects.get(id=staff_id)
            shift = Shift.objects.get(id=shift_id, staff_id=staff_id)
        except Staff.DoesNotExist:
            return Response({'error': 'Staff not found'}, status=status.HTTP_404_NOT_FOUND)
        except Shift.DoesNotExist:
            return Response({'error': 'Shift not found'}, status=status.HTTP_404_NOT_FOUND)

        shift.status = ShiftStatus.ENDED
        if not shift.end_time:
            shift.end_time = timezone.now()
        shift.save(update_fields=['status', 'end_time'])
        _log(staff, "end_shift", resource_type="shift", resource_id=shift.id)
        return Response({'message': 'Shift ended', 'shift': ShiftSerializer(shift).data}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def shifts(self, request):
        """List shifts (filter by staff_id)"""
        requester_id = request.query_params.get('requester_id')
        gw_manage = _gateway_can_manage_staff(request)
        if not requester_id and not gw_manage:
            return Response({'error': 'requester_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        requester = None
        if requester_id:
            try:
                requester = Staff.objects.get(id=requester_id)
            except Staff.DoesNotExist:
                if not gw_manage:
                    return Response({'error': 'Requester not found'}, status=status.HTTP_404_NOT_FOUND)

        if not gw_manage and not _has_permission(requester, PermissionType.VIEW_SHIFTS):
            return Response({'error': 'You do not have permission to view shifts'}, status=status.HTTP_403_FORBIDDEN)

        staff_id = request.query_params.get('staff_id')
        limit = int(request.query_params.get('limit', 50))

        qs = Shift.objects.all()
        if gw_manage or _has_permission(requester, PermissionType.MANAGE_SHIFTS):
            if staff_id:
                qs = qs.filter(staff_id=staff_id)
        else:
            qs = qs.filter(staff_id=requester_id)
        qs = qs.order_by('-start_time')[:limit]

        return Response({'count': qs.count(), 'shifts': ShiftSerializer(qs, many=True).data}, status=status.HTTP_200_OK)
