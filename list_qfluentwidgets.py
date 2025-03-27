import inspect
from qfluentwidgets import *

widget_classes = []
for name, obj in inspect.getmembers(globals()):
    if inspect.isclass(obj) and name.endswith(('Button', 'Slider', 'Widget', 'Layout', 'Label', 'Edit', 'View', 'Box', 'Dialog', 'Menu', 'Bar', 'Splitter')):
        widget_classes.append(name)

print('QFluentWidgets组件列表:')
for widget in sorted(widget_classes):
    print(f'- {widget}')