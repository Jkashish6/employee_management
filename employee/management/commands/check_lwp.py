from django.core.management.base import BaseCommand
from employee.views import check_leave_without_pay

class Command(BaseCommand):
    help = 'Check for unapproved leave days and mark as Leave Without Pay'

    def handle(self, *args, **options):
        self.stdout.write("Checking for Leave Without Pay...")
        check_leave_without_pay()
        self.stdout.write("Done.")