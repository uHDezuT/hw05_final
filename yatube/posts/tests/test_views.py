from django import forms
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from ..models import Post, Group, User, Follow


class PostPagesTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user('post_author')
        cls.group = Group.objects.create(
            title='Название группы',
            slug='slug',
            description='Описание группы',
        )
        cls.post = Post.objects.create(
            text='Текст',
            author=PostPagesTests.user,
            group=PostPagesTests.group,
        )
        cls.group_fake = Group.objects.create(
            title='Фейковая группа',
            slug='fake-slug',
            description='Описание фейк группы',
        )

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        cache.clear()

    def test_views_use_correct_template(self):
        """URL-адреса использует соответствующий шаблон."""

        def url(url, **kwargs):
            return reverse(url, kwargs=kwargs)

        urls = [
            url('posts:index'),
            url('posts:group_list', slug=self.group.slug),
            url('posts:profile', username=self.user.username),
            url('posts:post_detail', post_id=self.post.id),
            url('posts:post_edit', post_id=self.post.id),
            url('posts:post_create'),
        ]

        templates = [
            'posts/index.html',
            'posts/group_list.html',
            'posts/profile.html',
            'posts/post_detail.html',
            'posts/create_post.html',
            'posts/create_post.html',
        ]

        for url, template in zip(urls, templates):
            with self.subTest(url=url):
                response = self.authorized_client.get(url)
                self.assertTemplateUsed(response, template)

    def test_index_show_correct_context(self):
        """Словарь context, переданный в шаблон при вызове(с пажинатором)
        соответствует ожидаемому."""
        context = {reverse('posts:index'): self.post,
                   reverse('posts:group_list',
                           kwargs={'slug': self.group.slug,
                                   }): self.post,
                   reverse('posts:profile',
                           kwargs={'username': self.user.username,
                                   }): self.post,
                   }
        for reverse_page, post_object in context.items():
            with self.subTest(reverse_page=reverse_page):
                response = self.authorized_client.get(reverse_page)
                page_object = response.context['page_obj'][0]
                self.assertEqual(page_object.text, post_object.text)
                self.assertEqual(page_object.pub_date, post_object.pub_date)
                self.assertEqual(page_object.author, post_object.author)
                self.assertEqual(page_object.group, post_object.group)

    def test_group_page_show_correct_context(self):
        """Шаблон group сформирован с правильным контекстом."""
        context = {reverse('posts:group_list',
                           kwargs={'slug': self.group.slug}): self.group,
                   }
        for reverse_page, group in context.items():
            with self.subTest(reverse_page=reverse_page):
                response = self.authorized_client.get(reverse_page)
                group_object = response.context['group']
                self.assertEqual(group_object.title, group.title)
                self.assertEqual(group_object.slug, group.slug)
                self.assertEqual(group_object.description,
                                 group.description)

    def test_profile_show_correct_context(self):
        """Шаблон profile сформирован с правильным контекстом."""
        context = {reverse('posts:profile',
                           kwargs={'username': self.user.username}): self.user,
                   }
        for reverse_page, user in context.items():
            with self.subTest(reverse_page=reverse_page):
                response = self.authorized_client.get(reverse_page)
                author_object = response.context['author']
                self.assertEqual(author_object.id, user.id)
                self.assertEqual(author_object.username, user.username)

    def test_post_detail_show_correct_context(self):
        """Шаблон post_detail сформирован с правильным контекстом."""
        context = {reverse('posts:post_detail',
                           kwargs={'post_id': self.post.id}): self.user,
                   }
        for reverse_page, user_post in context.items():
            with self.subTest(reverse_page=reverse_page):
                response = self.authorized_client.get(reverse_page)
                author_object = response.context['user_post']
                self.assertEqual(author_object.id, user_post.id)
                self.assertEqual(author_object.author.username,
                                 user_post.username)

    def test_post_edit_correct_context(self):
        """Шаблон post_edit сформирован с правильным контекстом."""
        response = self.authorized_client.get(
            reverse('posts:post_edit', kwargs={'post_id': self.post.id})
        )
        form_fields = {
            'group': forms.fields.ChoiceField,
            'text': forms.fields.CharField,
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context['form'].fields[value]
                self.assertIsInstance(form_field, expected)

    def test_post_create_correct_context(self):
        """Шаблон post_create сформирован с правильным контекстом."""
        response = self.authorized_client.get(reverse('posts:post_create'))
        form_fields = {
            'group': forms.fields.ChoiceField,
            'text': forms.fields.CharField
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context['form'].fields[value]
                self.assertIsInstance(form_field, expected)

    def test_new_post_in_group(self):
        """Пост сохраняется в группе."""
        posts_count = Post.objects.filter(group=self.group).count()
        Post.objects.create(
            text='Текст для нового поста',
            author=self.user,
            group=self.group,
        )
        self.assertNotEqual(Post.objects.filter(
            group=self.group).count(), posts_count)

    def test_new_post_not_in_another_group(self):
        """Пост не сохраняется в группе, не предназначенной для него."""
        posts_count = Post.objects.filter(group=self.group_fake).count()
        Post.objects.create(
            text='Текст для нового поста',
            author=self.user,
            group=self.group,
        )
        self.assertEqual(Post.objects.filter(
            group=self.group_fake).count(), posts_count)

    def test_new_post_in_main_group_list_profile_pages(self):
        """Пост появляется на главной странице,
         странице пользователя и странице групп при указании группы"""
        response_dict = {
            reverse('posts:index'),
            reverse('posts:group_list', kwargs={'slug': self.group.slug}),
            reverse('posts:profile', kwargs={'username': self.user.username}),
        }
        for reverse_obj in response_dict:
            response = self.authorized_client.get(reverse_obj)
            post_count = len(response.context.get('page_obj').object_list)
            Post.objects.create(
                text='Текст для нового поста',
                author=self.user,
                group=self.group,
            )
            response = self.authorized_client.get(reverse_obj)
            post_count1 = len(response.context.get('page_obj').object_list)
            self.assertEqual(post_count + 1, post_count1)
            Post.objects.filter(
                text='Текст для нового поста').delete()


class CacheViewsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user('post_author')
        cls.group = Group.objects.create(
            title='Название группы',
            slug='slug',
            description='Описание группы',
        )
        cls.post = Post.objects.create(
            text='Текст',
            author=cls.user,
            group=cls.group,
        )

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        cache.clear()

    def test_cache_index(self):
        """Проверка хранения и очищения кэша для index."""
        response = self.authorized_client.get(reverse('posts:index'))
        posts = response.content
        Post.objects.create(
            text='New post',
            author=self.user,
        )
        response_old = self.authorized_client.get(
            reverse('posts:index')
        )
        old_posts = response_old.content
        self.assertEqual(
            old_posts,
            posts,
            'Не возвращает кэшированную страницу.'
        )
        cache.clear()
        response_new = self.authorized_client.get(reverse('posts:index'))
        new_posts = response_new.content
        self.assertNotEqual(old_posts, new_posts, 'Нет сброса кэша.')


class FollowViewsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user('post_author')
        cls.user_follow = User.objects.create_user('user_follow')
        cls.user_unfollow = User.objects.create_user('user_unfollow')
        cls.group = Group.objects.create(
            title='Название группы',
            slug='slug',
            description='Описание группы',
        )
        cls.post = Post.objects.create(
            text='Текст',
            author=cls.user,
            group=cls.group,
        )

    def setUp(self):
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        self.authorized_user_follow = Client()
        self.authorized_user_follow.force_login(self.user_follow)
        self.authorized_user_unfollow = Client()
        self.authorized_user_unfollow.force_login(self.user_unfollow)
        cache.clear()

    def test_follow(self):
        """Подписка на автора."""
        self.authorized_user_follow.get(
            reverse('posts:profile_follow',
                    kwargs={'username': self.user.username}))
        follower = Follow.objects.filter(
            user=self.user_follow,
            author=self.user
        ).exists()
        self.assertTrue(follower, 'Не работает подписка на автора')

    def test_unfollow(self):
        """Отписка от автора."""
        self.authorized_user_follow.get(reverse(
            'posts:profile_unfollow', kwargs={'username': self.user.username}
        )
        )
        follower = Follow.objects.filter(
            user=self.user_follow,
            author=self.user
        ).exists()
        self.assertFalse(
            follower,
            'Не работает отписка от автора'
        )
