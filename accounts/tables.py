from django_tables2 import tables

from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import OrganizationUser, Branch, City


class UserTable(tables.Table):
    search_full_name = tables.Column(verbose_name='ФИО')
    actions = tables.Column(verbose_name='Действия', empty_values=(), orderable=False)
    cities = tables.Column(verbose_name='Города', empty_values=())

    class Meta:
        fields = ('search_full_name', 'username', 'role', 'cities', 'actions')
        model = OrganizationUser
        attrs = {'class': 'table table-hover shadow table-responsive-xl'}

    def render_cities(self, record: OrganizationUser):
        """Отображение филиалов с иконкой"""
        if record.all_cities_access or record.is_manager:
            return format_html('<span class="badge badge-success">Все города</span>')

        cities = record.allowed_city_choices
        if not cities:
            return format_html('<span class="badge badge-warning">Нет городов</span>')

        cities_html = '<br>'.join(f'<span class="badge badge-primary mr-1">{city[1]}</span>' for city in cities)
        return format_html(cities_html)

    def render_actions(self, record: OrganizationUser):
        request_user_is_superuser = self.request.user.is_superuser
        change_denied = record.is_global_superuser and not request_user_is_superuser
        edit_link = f'''
               <a href="{reverse('accounts:edit', args=(record.pk,))}" class="btn btn-outline-info" 
                    title="Редактировать">
                    <i class="material-icons">edit</i>
               </a>
           ''' if not change_denied else ''
        change_pass_link = f'''
               <a href="{reverse('accounts:change_password', args=(record.pk,))}" class="btn btn-outline-warning" 
                    title="Сменить пароль">
                    <i class="material-icons">lock_open</i>
               </a>
           ''' if not change_denied else ''
        auth_link = f'''
               <a href="{reverse('identity:authorize')}?username={record.username}" 
                  class="btn btn-outline-primary" title="Войти">
                    <i class="material-icons">login</i>
               </a>
           ''' if request_user_is_superuser else ''
        delete_url = reverse('accounts:delete', args=(record.pk,))
        delete_link = f'''
               <button class="btn btn-outline-danger" onclick="confirmDelete('{record.username}', '{delete_url}')"
                       title="Удалить пользователя">
                   <i class="material-icons">delete</i>
               </button>
           ''' if not change_denied else ''
        return mark_safe(f'<div class="text-nowrap">{edit_link}{change_pass_link}{auth_link}{delete_link}<div>')


class BranchTable(tables.Table):
    title = tables.Column('Название', empty_values=())

    class Meta:
        fields = ('title', 'is_active')
        model = Branch
        attrs = {'class': 'table table-hover shadow table-responsive-sm'}

    def render_title(self, record: Branch):
        update_url = f'''
                <a class="font-weight-bold" href={reverse("accounts:branch_update",
                                                          args=(record.pk,))} title="Изменение">
                    {record}
                </a>
            '''
        return mark_safe(f'<div class="text-nowrap">{update_url}<div>')

    def order_title(self, queryset, is_descending):
        queryset = queryset.order_by(('-' if is_descending else '') + 'city__name',
                                     ('-' if is_descending else '') + 'name')
        return queryset, True


class CityTable(tables.Table):
    class Meta:
        fields = ('name', 'is_active')
        model = City
        attrs = {'class': 'table table-hover shadow'}

    def render_name(self, record: City):
        update_url = f'''
                <a class="font-weight-bold" href={reverse("accounts:city_update", args=(record.pk,))} title="Изменение">
                    {record}
                </a>
            '''
        return mark_safe(f'<div class="text-nowrap">{update_url}<div>')
