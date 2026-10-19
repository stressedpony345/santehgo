from django.core.management.base import BaseCommand, CommandError

from core.models import SubCategory


IMAGE_BY_SERVICE = {
    "Выезд сантехника и первичная диагностика": "diagnosis-visit.png",
    "Комплексное обследование инженерных систем": "diagnosis-systems.png",
    "Консультация по улучшению систем": "consultation.png",
    "Планирование и смета работ": "planning.png",
    "Подбор и закупка материалов": "materials.png",
    "Полное сопровождение под ключ": "full-support.png",
    "Кухонная мойка": "kitchen-sink.png",
    "Кухонный смеситель": "kitchen-faucet.png",
    "Сифон для кухонной мойки": "kitchen-siphon.png",
    "Измельчитель пищевых отходов": "food-disposer.png",
    "Стиральная машина": "washing-machine.png",
    "Сушильная машина": "dryer.png",
    "Посудомоечная машина": "dishwasher.png",
    "Смеситель для ванной": "bath-faucet.png",
    "Смеситель для раковины": "sink-faucet.png",
    "Душевая система": "shower-system.png",
    "Водоразборный кран": "water-tap.png",
    "Проточный фильтр под мойку": "flow-filter.png",
    "Система обратного осмоса": "reverse-osmosis.png",
    "Магистральный фильтр": "main-filter.png",
    "Система умягчения воды": "water-softener.png",
    "Акриловая или стальная ванна": "bathtub.png",
    "Чугунная ванна": "cast-iron-bathtub.png",
    "Гидромассажная ванна": "hydromassage-bathtub.png",
    "Душевая кабина": "shower-cabin.png",
    "Душевой уголок или ограждение": "shower-enclosure.png",
    "Душевой поддон": "shower-tray.png",
    "Душевой трап": "shower-drain.png",
    "Раковина с тумбой": "vanity-sink.png",
    "Подвесная раковина": "wall-sink.png",
    "Раковина с пьедесталом": "pedestal-sink.png",
    "Накладная или встраиваемая раковина": "countertop-sink.png",
    "Напольный унитаз": "floor-toilet.png",
    "Подвесной унитаз": "wall-toilet.png",
    "Инсталляция для унитаза": "concealed-cistern.png",
    "Биде": "bidet-shower.png",
    "Гигиенический душ": "bidet-shower.png",
    "Накопительный водонагреватель": "water-heater.png",
    "Проточный водонагреватель": "water-heater.png",
    "Водяной полотенцесушитель": "towel-rail.png",
    "Электрический полотенцесушитель": "towel-rail.png",
    "Счётчик холодной или горячей воды": "meters.png",
    "Счётчик тепла": "meters.png",
    "Гибкая подводка и РВД": "leak-protection.png",
    "Система защиты от протечек": "leak-protection.png",
    "Фильтр грубой очистки": "filters-valves.png",
    "Обратный клапан": "filters-valves.png",
    "Редуктор давления": "filters-valves.png",
    "Засор кухонной мойки": "drain-cleaning.png",
    "Засор раковины, ванны или душа": "drain-cleaning.png",
    "Засор унитаза": "drain-cleaning.png",
    "Засор канализационной трубы": "drain-cleaning.png",
    "Гидродинамическая прочистка": "drain-cleaning.png",
    "Внутренняя канализация ПВХ": "sewer-pipes.png",
    "Чугунная канализация": "sewer-pipes.png",
    "Перенос канализационной точки": "sewer-pipes.png",
    "Трубы из сшитого полиэтилена": "water-pipes.png",
    "Металлопластиковые трубы": "water-pipes.png",
    "Полипропиленовые трубы": "water-pipes.png",
    "Коллекторная разводка": "manifold.png",
    "Радиатор отопления": "radiator.png",
    "Конвектор отопления": "radiator.png",
    "Термостатический клапан": "heating-service.png",
    "Промывка отопительного прибора": "heating-service.png",
    "Стояк холодной или горячей воды": "risers.png",
    "Стояк отопления": "risers.png",
    "Канализационный стояк": "risers.png",
    "Шаровой кран": "shutoff-valves.png",
    "Вводной запорный кран": "shutoff-valves.png",
    "Ремонт трубопровода": "water-pipes.png",
    "Перенос трубопровода": "water-pipes.png",
}


class Command(BaseCommand):
    help = "Assign generated object-only images to all catalog services."

    def handle(self, *args, **options):
        services = list(SubCategory.objects.all())
        names = {service.name for service in services}
        missing = names - IMAGE_BY_SERVICE.keys()
        unknown = IMAGE_BY_SERVICE.keys() - names
        if missing or unknown:
            details = []
            if missing:
                details.append(f"without mapping: {', '.join(sorted(missing))}")
            if unknown:
                details.append(f"not found in DB: {', '.join(sorted(unknown))}")
            raise CommandError("; ".join(details))

        for service in services:
            filename = IMAGE_BY_SERVICE[service.name]
            service.image = f"services/generated/{filename}"
        SubCategory.objects.bulk_update(services, ["image"])
        self.stdout.write(self.style.SUCCESS(f"Assigned images to {len(services)} services."))
