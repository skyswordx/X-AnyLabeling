import re
import json

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtWidgets import QColorDialog, QTableWidgetItem, QTableWidget, QCheckBox

from .. import utils
from ..logger import logger


# TODO(unknown):
# - Calculate optimal position so as not to go out of screen area.


class LabelColorButton(QtWidgets.QWidget):
    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.color = color
        self.parent = parent
        self.init_ui()

    def init_ui(self):
        self.color_label = QtWidgets.QLabel()
        self.color_label.setFixedSize(15, 15)
        self.color_label.setStyleSheet(f'background-color: {self.color.name()}; border: 1px solid transparent; border-radius: 10px;')
        
        self.layout = QtWidgets.QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.color_label)
        
    def set_color(self, color):
        self.color = color
        self.color_label.setStyleSheet(f'background-color: {self.color.name()}; border: 1px solid transparent; border-radius: 10px;')

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.parent.change_color(self)


class LabelModifyDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, opacity=128):
        super(LabelModifyDialog, self).__init__(parent)
        self.parent = parent
        self.opacity = opacity
        self.label_file_list = parent.get_label_file_list()
        self.hidden_cls = parent.hidden_cls
        self.init_label_info()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Label Change Manager")
        self.setGeometry(100, 100, 600, 400)

        self.table_widget = QTableWidget(self)
        self.table_widget.setColumnCount(5)
        self.table_widget.setHorizontalHeaderLabels(
            ["Category", "Delete", "New Value", "Hidden", "Color"]
        )

        # Set header font and alignment
        for i in range(5):
            self.table_widget.horizontalHeaderItem(i).setFont(
                QFont("Arial", 8, QFont.Bold)
            )
            self.table_widget.horizontalHeaderItem(i).setTextAlignment(
                QtCore.Qt.AlignCenter
            )

        self.buttons_layout = QtWidgets.QHBoxLayout()

        self.cancel_button = QtWidgets.QPushButton("Cancel", self)
        self.cancel_button.clicked.connect(self.reject)

        self.confirm_button = QtWidgets.QPushButton("Confirm", self)
        self.confirm_button.clicked.connect(self.confirm_changes)

        self.buttons_layout.addWidget(self.cancel_button)
        self.buttons_layout.addWidget(self.confirm_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.table_widget)
        layout.addLayout(self.buttons_layout)

        self.populate_table()

    def populate_table(self):
        for i, (label, info) in enumerate(self.parent.label_info.items()):
            self.table_widget.insertRow(i)

            class_item = QTableWidgetItem(label)
            class_item.setFlags(class_item.flags() ^ QtCore.Qt.ItemIsEditable)

            delete_checkbox = QCheckBox()
            delete_checkbox.setChecked(info["delete"])
            delete_checkbox.setIcon(QtGui.QIcon(":/images/images/delete.png"))
            delete_checkbox.stateChanged.connect(
                lambda state, row=i: self.on_delete_checkbox_changed(
                    row, state
                )
            )

            hidden_checkbox = QCheckBox()
            hidden_checkbox.setChecked(info["hidden"])
            hidden_checkbox.setIcon(QtGui.QIcon(":/images/images/hidden.png"))
            hidden_checkbox.stateChanged.connect(
                lambda state, row=i: self.on_hidden_checkbox_changed(
                    row, state
                )
            )

            delete_checkbox.setCheckable(not info["hidden"])

            value_item = QTableWidgetItem(info["value"] if info["value"] else "")
            value_item.setFlags(
                value_item.flags() & ~QtCore.Qt.ItemIsEditable
                if info["delete"]
                else value_item.flags() | QtCore.Qt.ItemIsEditable
            )
            value_item.setBackground(
                QtGui.QColor("lightgray")
                if info["delete"]
                else QtGui.QColor("white")
            )

            color = QColor(*info['color'])
            color.setAlpha(info['opacity'])
            color_button = LabelColorButton(color, self)
            color_button.setParent(self.table_widget)
            self.table_widget.setItem(i, 0, class_item)
            self.table_widget.setCellWidget(i, 1, delete_checkbox)
            self.table_widget.setItem(i, 2, value_item)
            self.table_widget.setCellWidget(i, 3, hidden_checkbox)
            self.table_widget.setCellWidget(i, 4, color_button)

    def change_color(self, button):
        row = self.table_widget.indexAt(button.pos()).row()
        current_color = self.parent.label_info[self.table_widget.item(row, 0).text()]['color']
        color = QColorDialog.getColor(QColor(*current_color), self)
        if color.isValid():
            self.parent.label_info[self.table_widget.item(row, 0).text()]['color'] = [color.red(), color.green(), color.blue()]
            self.parent.label_info[self.table_widget.item(row, 0).text()]['opacity'] = color.alpha()
            button.set_color(color)

    def on_delete_checkbox_changed(self, row, state):
        value_item = self.table_widget.item(row, 2)
        delete_checkbox = self.table_widget.cellWidget(row, 1)
        hidden_checkbox = self.table_widget.cellWidget(row, 3)

        if state == QtCore.Qt.Checked:
            value_item.setFlags(value_item.flags() & ~QtCore.Qt.ItemIsEditable)
            value_item.setBackground(QtGui.QColor("lightgray"))
            delete_checkbox.setCheckable(True)
            hidden_checkbox.setCheckable(False)
        else:
            value_item.setFlags(value_item.flags() | QtCore.Qt.ItemIsEditable)
            value_item.setBackground(QtGui.QColor("white"))
            delete_checkbox.setCheckable(False)
            hidden_checkbox.setCheckable(True)

        if value_item.text():
            delete_checkbox.setCheckable(False)
        else:
            delete_checkbox.setCheckable(True)

    def on_hidden_checkbox_changed(self, row, state):
        delete_checkbox = self.table_widget.cellWidget(row, 1)

        if state == QtCore.Qt.Checked:
            delete_checkbox.setCheckable(False)
        else:
            delete_checkbox.setCheckable(True)

    def confirm_changes(self):
        self.hidden_cls.clear()

        total_num = self.table_widget.rowCount()
        if total_num == 0:
            self.reject()
            return

        # Temporary dictionary to handle changes
        updated_label_info = {}

        for i in range(total_num):
            label = self.table_widget.item(i, 0).text()
            delete_checkbox = self.table_widget.cellWidget(i, 1)
            hidden_checkbox = self.table_widget.cellWidget(i, 3)
            value_item = self.table_widget.item(i, 2)

            is_delete = delete_checkbox.isChecked()
            new_value = value_item.text()
            is_hidden = hidden_checkbox.isChecked()

            # Update the label info in the temporary dictionary
            self.parent.label_info[label]["delete"] = is_delete
            self.parent.label_info[label]["value"] = new_value

            # Handle hidden classes
            if not is_delete and is_hidden:
                self.hidden_cls.append(
                    label if new_value == "" else new_value
                )

            # Update the color
            color = self.parent.label_info[label]["color"]
            self.parent.unique_label_list.update_item_color(
                label, color, self.opacity
            )

            # Handle delete and change of labels
            if is_delete:
                self.parent.unique_label_list.remove_items_by_label(label)
                continue  # Skip adding this to updated_label_info to effectively delete it
            elif new_value:
                self.parent.unique_label_list.remove_items_by_label(label)
                updated_label_info[new_value] = self.parent.label_info[label]
            else:
                updated_label_info[label] = self.parent.label_info[label]

        # Try to modify labels
        if self.modify_label():
            # If modification is successful, update self.parent.label_info
            self.parent.label_info = updated_label_info
            QtWidgets.QMessageBox.information(
                self,
                "Success",
                "Labels modified successfully!",
            )
            self.accept()
        else:
            QtWidgets.QMessageBox.warning(
                self, "Warning", "An error occurred while updating the labels."
            )

    def modify_label(self):
        try:
            for label_file in self.label_file_list:
                with open(label_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                src_shapes, dst_shapes = data["shapes"], []
                for shape in src_shapes:
                    label = shape["label"]
                    if self.parent.label_info[label]["delete"]:
                        continue
                    if self.parent.label_info[label]["value"]:
                        shape["label"] = self.parent.label_info[label]["value"]
                    dst_shapes.append(shape)
                data["shapes"] = dst_shapes
                with open(label_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error occurred while updating labels: {e}")
            return False

    def init_label_info(self):
        classes = set()

        for label_file in self.label_file_list:
            with open(label_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            shapes = data.get("shapes", [])
            for shape in shapes:
                label = shape["label"]
                classes.add(label)

        for c in sorted(classes):
            # Update unique label list
            if not self.parent.unique_label_list.find_items_by_label(c):
                unique_label_item = self.parent.unique_label_list.create_item_from_label(c)
                self.parent.unique_label_list.addItem(unique_label_item)
                rgb = self.parent._get_rgb_by_label(c, skip_label_info=True)
                self.parent.unique_label_list.set_item_label(
                    unique_label_item, c, rgb, self.opacity
                )
            # Update label info
            color = [0, 0, 0]
            opacity = 255
            items = self.parent.unique_label_list.find_items_by_label(c)
            for item in items:
                qlabel = self.parent.unique_label_list.itemWidget(item)
                if qlabel:
                    style_sheet = qlabel.styleSheet()
                    start_index = style_sheet.find('rgba(') + 5
                    end_index = style_sheet.find(')', start_index)
                    rgba_color = style_sheet[start_index:end_index].split(',')
                    rgba_color = [int(x.strip()) for x in rgba_color]
                    color = rgba_color[:-1]
                    opacity = rgba_color[-1]
                    break
            self.parent.label_info[c] = dict(
                delete=False, value=None, hidden=c in self.hidden_cls,
                color=color, opacity=opacity
            )


class TextInputDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Text Input Dialog")

        layout = QtWidgets.QVBoxLayout()

        self.label = QtWidgets.QLabel("Enter the text prompt below:")
        self.text_input = QtWidgets.QLineEdit()

        self.ok_button = QtWidgets.QPushButton("OK")
        self.cancel_button = QtWidgets.QPushButton("Cancel")

        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        layout.addWidget(self.label)
        layout.addWidget(self.text_input)
        layout.addWidget(self.ok_button)
        layout.addWidget(self.cancel_button)

        self.setLayout(layout)

    def get_input_text(self):
        result = self.exec_()
        if result == QtWidgets.QDialog.Accepted:
            return self.text_input.text()
        else:
            return ""


class LabelQLineEdit(QtWidgets.QLineEdit):
    def __init__(self) -> None:
        super().__init__()
        self.list_widget = None

    def set_list_widget(self, list_widget):
        self.list_widget = list_widget

    # QT Overload
    def keyPressEvent(self, e):
        if e.key() in [QtCore.Qt.Key_Up, QtCore.Qt.Key_Down]:
            self.list_widget.keyPressEvent(e)
        else:
            super(LabelQLineEdit, self).keyPressEvent(e)


class LabelDialog(QtWidgets.QDialog):
    def __init__(
        self,
        text=None,
        parent=None,
        labels=None,
        sort_labels=True,
        show_text_field=True,
        completion="startswith",
        fit_to_content=None,
        flags=None,
        difficult=False,
    ):
        if text is None:
            text = QCoreApplication.translate(
                "LabelDialog", "Enter object label"
            )

        if fit_to_content is None:
            fit_to_content = {"row": False, "column": True}
        self._fit_to_content = fit_to_content

        super(LabelDialog, self).__init__(parent)
        self.edit = LabelQLineEdit()
        self.edit.setPlaceholderText(text)
        self.edit.setValidator(utils.label_validator())
        self.edit.editingFinished.connect(self.postprocess)
        if flags:
            self.edit.textChanged.connect(self.update_flags)
        self.edit_group_id = QtWidgets.QLineEdit()
        self.edit_group_id.setPlaceholderText(self.tr("Group ID"))
        self.edit_group_id.setValidator(
            QtGui.QRegularExpressionValidator(
                QtCore.QRegularExpression(r"\d*"), None
            )
        )
        self.edit_difficult = QtWidgets.QCheckBox("useDifficult")
        self.edit_difficult.setChecked(difficult)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        if show_text_field:
            layout_edit = QtWidgets.QHBoxLayout()
            layout_edit.addWidget(self.edit, 6)
            layout_edit.addWidget(self.edit_group_id, 2)
            layout.addLayout(layout_edit)
        # buttons
        self.button_box = bb = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            QtCore.Qt.Horizontal,
            self,
        )
        bb.button(bb.Ok).setIcon(utils.new_icon("done"))
        bb.button(bb.Cancel).setIcon(utils.new_icon("undo"))
        bb.accepted.connect(self.validate)
        bb.rejected.connect(self.reject)

        layout_button = QtWidgets.QHBoxLayout()
        layout_button.addWidget(self.edit_difficult)
        layout_button.addWidget(self.button_box)
        layout.addLayout(layout_button)

        # label_list
        self.label_list = QtWidgets.QListWidget()
        if self._fit_to_content["row"]:
            self.label_list.setHorizontalScrollBarPolicy(
                QtCore.Qt.ScrollBarAlwaysOff
            )
        if self._fit_to_content["column"]:
            self.label_list.setVerticalScrollBarPolicy(
                QtCore.Qt.ScrollBarAlwaysOff
            )
        self._sort_labels = sort_labels
        if labels:
            self.label_list.addItems(labels)
        if self._sort_labels:
            self.label_list.sortItems()
        else:
            self.label_list.setDragDropMode(
                QtWidgets.QAbstractItemView.InternalMove
            )
        self.label_list.currentItemChanged.connect(self.label_selected)
        self.label_list.itemDoubleClicked.connect(self.label_double_clicked)
        self.edit.set_list_widget(self.label_list)
        layout.addWidget(self.label_list)
        # label_flags
        if flags is None:
            flags = {}
        self._flags = flags
        self.flags_layout = QtWidgets.QVBoxLayout()
        self.reset_flags()
        layout.addItem(self.flags_layout)
        self.edit.textChanged.connect(self.update_flags)
        # text edit
        self.edit_description = QtWidgets.QTextEdit()
        self.edit_description.setPlaceholderText("Label description")
        self.edit_description.setFixedHeight(50)
        layout.addWidget(self.edit_description)
        self.setLayout(layout)
        # completion
        completer = QtWidgets.QCompleter()
        if completion == "startswith":
            completer.setCompletionMode(QtWidgets.QCompleter.InlineCompletion)
            # Default settings.
            # completer.setFilterMode(QtCore.Qt.MatchStartsWith)
        elif completion == "contains":
            completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
            completer.setFilterMode(QtCore.Qt.MatchContains)
        else:
            raise ValueError(f"Unsupported completion: {completion}")
        completer.setModel(self.label_list.model())
        self.edit.setCompleter(completer)
        # Save last label
        self._last_label = ""

    def get_last_label(self):
        return self._last_label

    def add_label_history(self, label):
        self._last_label = label
        if self.label_list.findItems(label, QtCore.Qt.MatchExactly):
            return
        self.label_list.addItem(label)
        if self._sort_labels:
            self.label_list.sortItems()

    def label_selected(self, item):
        self.edit.setText(item.text())

    def validate(self):
        text = self.edit.text()
        if hasattr(text, "strip"):
            text = text.strip()
        else:
            text = text.trimmed()
        if text:
            self.accept()

    def label_double_clicked(self, _):
        self.validate()

    def postprocess(self):
        text = self.edit.text()
        if hasattr(text, "strip"):
            text = text.strip()
        else:
            text = text.trimmed()
        self.edit.setText(text)

    def update_flags(self, label_new):
        # keep state of shared flags
        flags_old = self.get_flags()

        flags_new = {}
        for pattern, keys in self._flags.items():
            if re.match(pattern, label_new):
                for key in keys:
                    flags_new[key] = flags_old.get(key, False)
        self.set_flags(flags_new)

    def delete_flags(self):
        for i in reversed(range(self.flags_layout.count())):
            item = self.flags_layout.itemAt(i).widget()
            self.flags_layout.removeWidget(item)
            item.setParent(None)

    def reset_flags(self, label=""):
        flags = {}
        for pattern, keys in self._flags.items():
            if re.match(pattern, label):
                for key in keys:
                    flags[key] = False
        self.set_flags(flags)

    def set_flags(self, flags):
        self.delete_flags()
        for key in flags:
            item = QtWidgets.QCheckBox(key, self)
            item.setChecked(flags[key])
            self.flags_layout.addWidget(item)
            item.show()

    def get_flags(self):
        flags = {}
        for i in range(self.flags_layout.count()):
            item = self.flags_layout.itemAt(i).widget()
            flags[item.text()] = item.isChecked()
        return flags

    def get_group_id(self):
        group_id = self.edit_group_id.text()
        if group_id:
            return int(group_id)
        return None

    def get_description(self):
        return self.edit_description.toPlainText()

    def get_difficult_state(self):
        return self.edit_difficult.isChecked()

    def pop_up(
        self,
        text=None,
        move=True,
        flags=None,
        group_id=None,
        description=None,
        difficult=False,
    ):
        if self._fit_to_content["row"]:
            self.label_list.setMinimumHeight(
                self.label_list.sizeHintForRow(0) * self.label_list.count() + 2
            )
        if self._fit_to_content["column"]:
            self.label_list.setMinimumWidth(
                self.label_list.sizeHintForColumn(0) + 2
            )
        # if text is None, the previous label in self.edit is kept
        if text is None:
            text = self.edit.text()
        # description is always initialized by empty text c.f., self.edit.text
        if description is None:
            description = ""
        self.edit_description.setPlainText(description)
        if flags:
            self.set_flags(flags)
        else:
            self.reset_flags(text)
        if difficult:
            self.edit_difficult.setChecked(True)
        else:
            self.edit_difficult.setChecked(False)
        self.edit.setText(text)
        self.edit.setSelection(0, len(text))
        if group_id is None:
            self.edit_group_id.clear()
        else:
            self.edit_group_id.setText(str(group_id))
        items = self.label_list.findItems(text, QtCore.Qt.MatchFixedString)
        if items:
            if len(items) != 1:
                logger.warning("Label list has duplicate '%s'", text)
            self.label_list.setCurrentItem(items[0])
            row = self.label_list.row(items[0])
            self.edit.completer().setCurrentRow(row)
        self.edit.setFocus(QtCore.Qt.PopupFocusReason)
        if move:
            self.move(QtGui.QCursor.pos())
        if self.exec_():
            return (
                self.edit.text(),
                self.get_flags(),
                self.get_group_id(),
                self.get_description(),
                self.get_difficult_state(),
            )

        return None, None, None, None, False
