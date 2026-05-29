"""FactoryBoy factories for tasks models"""

import factory


class ProjectFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'tasks.Project'
        django_get_or_create = ('code',)

    name = factory.Sequence(lambda n: f'项目_{n:04d}')
    code = factory.Sequence(lambda n: f'PRJ{n:04d}')
    status = 'active'
    progress = 0

    @factory.post_generation
    def company(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            self.company = extracted
            self.save()
