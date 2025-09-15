from PySide6 import QtCore, QtGui, QtWidgets
from pathlib import Path
from .vcs import Repo
import difflib
import json
import csv
import os
import base64

class Timeline(QtWidgets.QWidget):
    selectionChanged = QtCore.Signal(list)  # Emit the selected list
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.points = []
        self.selected = []
        self.setMinimumHeight(90)
        self.spacing = 150  # Fixed spacing between snapshot points (pixels)
        self.margin = 20  # Margin on left/right

    def set_points(self, pts):
        print(f"Setting timeline points: {len(pts)} snapshots, first={pts[0][0] if pts else 'None'}")  # Debug
        self.points = pts
        # Dynamically set width based on total snapshots for scrolling
        total_width = self.margin * 2 + max(0, len(pts) - 1) * self.spacing
        self.setFixedWidth(max(600, total_width))  # Minimum 600px for small timelines
        print(f"Timeline width set to {self.width()}px for {len(pts)} snapshots")  # Debug
        self.update()  # Force repaint

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        r = self.rect()
        p.fillRect(r, self.palette().window())
        if not self.points:
            p.drawText(r, QtCore.Qt.AlignCenter, "No snapshots")
            return
        y = r.height() // 2
        for i, (name, manifest) in enumerate(self.points):
            x = self.margin + i * self.spacing
            # Skip drawing if outside visible area (for efficiency, though Qt clips)
            if x < r.left() - self.spacing or x > r.right() + self.spacing:
                continue
            color = QtGui.QColor('#f39c12') if name in self.selected else QtGui.QColor('#2b7bf6')
            p.setBrush(color)
            p.drawEllipse(QtCore.QPoint(x, y), 7, 7)
            iso = manifest.get('iso', '')
            label = iso.replace('Z', '')[:19].replace('T', ' ')
            p.drawText(x - 60, y + 25, 120, 18, QtCore.Qt.AlignCenter, label)
        print(f"Painting timeline: {len(self.points)} total snapshots")  # Debug

    def mouseReleaseEvent(self, event):
        pos = event.position().toPoint()
        y = self.rect().height() // 2
        for i, (name, _) in enumerate(self.points):
            x = self.margin + i * self.spacing
            if QtCore.QRect(x - 8, y - 8, 16, 16).contains(pos):
                if name in self.selected:
                    self.selected.remove(name)
                else:
                    self.selected.append(name)
                    if len(self.selected) > 2:
                        self.selected.pop(0)
                print(f"Mouse click detected, selected snapshot(s): {self.selected}, total selected: {len(self.selected)}")  # Debug
                self.selectionChanged.emit(self.selected)  # Emit the current selected list
                self.update()
                return

class MainWindow(QtWidgets.QMainWindow):
    refreshRequested = QtCore.Signal()

    def __init__(self, repo: Repo):
        super().__init__()
        self.repo = repo
        self.setWindowTitle(f"pyvcs — {repo.root}")
        self.resize(1100, 800)
        self.refreshRequested.connect(self.refresh_snapshots)
        self._setup_ui()
        self._start_watcher()

    def _setup_ui(self):
        w, v = QtWidgets.QWidget(), QtWidgets.QVBoxLayout()
        w.setLayout(v)
        self.setCentralWidget(w)
        ctrl = QtWidgets.QHBoxLayout()
        self.btn_manual = QtWidgets.QPushButton('Manual snapshot')
        self.btn_manual.clicked.connect(self.on_manual_snapshot)
        self.btn_edit_message = QtWidgets.QPushButton('Edit Message')
        self.btn_edit_message.clicked.connect(self.edit_snapshot_message)
        self.btn_edit_message.setVisible(False)  # Hidden by default
        self.btn_export_overview = QtWidgets.QPushButton('Export Overview')
        self.btn_export_overview.clicked.connect(self.export_overview)
        self.btn_show_snapshot = QtWidgets.QPushButton('Show Me the Snapshot')
        self.btn_show_snapshot.clicked.connect(self.show_snapshot)
        self.btn_show_snapshot.setEnabled(False)  # Disabled by default
        self.lbl_status = QtWidgets.QLabel('')
        ctrl.addWidget(self.btn_manual)
        ctrl.addWidget(self.btn_edit_message)
        ctrl.addWidget(self.btn_export_overview)
        ctrl.addWidget(self.btn_show_snapshot)
        ctrl.addWidget(self.lbl_status)
        ctrl.addStretch()
        v.addLayout(ctrl)
        
        # Wrap Timeline in QScrollArea with explicit signal connection
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.timeline = Timeline()
        self.scroll_area.setWidget(self.timeline)
        self.scroll_area.setMinimumHeight(110)  # Enough for timeline + scrollbar
        self.timeline.selectionChanged.connect(self.on_timeline_selection_change)
        v.addWidget(self.scroll_area)
        
        splitter = QtWidgets.QSplitter()
        v.addWidget(splitter, 1)
        self.model = QtGui.QStandardItemModel()
        self.model.setHorizontalHeaderLabels(['Name', 'hash', 'size'])
        self.tree = QtWidgets.QTreeView()
        self.tree.setModel(self.model)
        self.tree.clicked.connect(self.on_tree_clicked)
        splitter.addWidget(self.tree)
        right = QtWidgets.QWidget()
        rv = QtWidgets.QVBoxLayout(right)
        self.summary, self.diff = QtWidgets.QTextEdit(), QtWidgets.QTextEdit()
        self.summary.setReadOnly(True)
        self.diff.setReadOnly(True)
        self.diff.setFont(QtGui.QFont('Courier', 10))
        rv.addWidget(self.summary)
        rv.addWidget(self.diff, 1)
        splitter.addWidget(right)
        style = self.style()
        self.icon_folder, self.icon_file = style.standardIcon(QtWidgets.QStyle.SP_DirIcon), style.standardIcon(QtWidgets.QStyle.SP_FileIcon)
        self.refresh_snapshots()

    def _start_watcher(self):
        from .watcher import AutoWatcher
        def schedule_refresh():
            print("Emitting refreshRequested signal from watcher")  # Debug
            self.refreshRequested.emit()
        self.watcher = AutoWatcher(self.repo, schedule_refresh)
        self.watcher.start()
        print("Watcher started, monitoring:", str(self.repo.root))  # Debug

    def refresh_snapshots(self):
        import time
        for _ in range(3):  # Retry up to 3 times
            items = self.repo.list_snapshots()
            print(f"Refreshing timeline: attempt {_+1}, {len(items)} snapshots loaded, first={items[0][0] if items else 'None'}")  # Debug
            self.timeline.set_points(items)
            self.timeline.update()
            self.lbl_status.setText(f"{len(items)} snapshots")
            if items:
                # Auto-select latest snapshot if none selected (to show files in tree)
                if not self.timeline.selected and self.timeline.points:
                    last_name = self.timeline.points[-1][0]
                    self.timeline.selected = [last_name]
                    self.timeline.selectionChanged.emit(self.timeline.selected)  # Trigger tree population
                    self.timeline.update()
                    print(f"Auto-selected latest snapshot: {last_name}")  # Debug
                # Auto-scroll to the end to show latest snapshots
                QtCore.QTimer.singleShot(0, lambda: self.scroll_area.horizontalScrollBar().setValue(self.scroll_area.horizontalScrollBar().maximum()))
                break
            print("No snapshots loaded, retrying...")
            time.sleep(0.2)
        else:
            print("Warning: No snapshots loaded after retries")
        # Update button state based on snapshot_overview.csv existence
        self.btn_show_snapshot.setEnabled((self.repo.root / 'snapshot_overview.csv').exists())

    def on_manual_snapshot(self):
        self.lbl_status.setText('Snapshotting...')
        import threading
        def worker():
            try:
                _, created = self.repo.snapshot(message='manual')
                print(f"Manual snapshot: created={created}")  # Debug
                import time
                time.sleep(0.2)
                self.refreshRequested.emit()
                QtCore.QTimer.singleShot(200, lambda: self.lbl_status.setText('Ready' if created else 'No changes'))
            except Exception as e:
                print(f"Manual snapshot error: {e}")
                QtCore.QTimer.singleShot(200, lambda: self.lbl_status.setText(f'Error: {e}'))
        threading.Thread(target=worker, daemon=True).start()

    def on_timeline_selection_change(self, selected):
        print(f"Timeline selection changed: {selected}")  # Debug
        self.timeline.selected = selected if selected else self.timeline.selected  # Sync selected state
        sel = self.timeline.selected
        # Toggle Edit Message button visibility
        self.btn_edit_message.setVisible(len(sel) == 1)
        if len(sel) == 0:
            self.model.removeRows(0, self.model.rowCount()); self.summary.clear(); self.diff.clear(); return
        if len(sel) == 1:
            m = self.repo.load_manifest(sel[0])
            print(f"Loading manifest for {sel[0]}, files: {list(m.get('files', {}).keys())}")  # Debug manifest content
            self.populate_tree_single(m)
            self.summary.setPlainText(f"Snapshot: {sel[0]}\n{m.get('iso')}\n{m.get('message','')}")
            self.diff.clear()
            return
        a, b = sel; ma, mb = self.repo.load_manifest(a), self.repo.load_manifest(b)
        print(f"Comparing {a} (files: {list(ma.get('files', {}).keys())}) with {b} (files: {list(mb.get('files', {}).keys())})")  # Debug
        self.populate_tree_union(ma, mb)
        added, removed, common = set(mb['files']) - set(ma['files']), set(ma['files']) - set(mb['files']), set(ma['files']) & set(mb['files'])
        modified = {p for p in common if ma['files'].get(p, {}).get('hash', '') != mb['files'].get(p, {}).get('hash', '')}
        unchanged = len(common) - len(modified)
        self.summary.setPlainText(f"A: {a}\nB: {b}\nAdded: {len(added)}\nRemoved: {len(removed)}\nModified: {len(modified)}\nUnchanged: {unchanged}")
        # Show diff for two snapshots
        if len(sel) == 2:
            self.show_diff_between_snapshots(a, b, ma, mb)

    def edit_snapshot_message(self):
        if len(self.timeline.selected) != 1:
            return  # Shouldn't happen due to button visibility
        current_name = self.timeline.selected[0]
        current_manifest = self.repo.load_manifest(current_name)
        current_message = current_manifest.get('message', '')
        
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Edit Snapshot Message")
        layout = QtWidgets.QVBoxLayout()
        
        label = QtWidgets.QLabel(f"Current message: {current_message}")
        layout.addWidget(label)
        
        text_edit = QtWidgets.QTextEdit(current_message)
        layout.addWidget(text_edit)
        
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            new_message = text_edit.toPlainText().strip()
            if new_message != current_message:
                manifest_path = self.repo.manifests / f"{current_name}"
                with open(manifest_path, 'r') as f:
                    data = json.load(f)
                data['message'] = new_message
                with open(manifest_path, 'w') as f:
                    json.dump(data, f, indent=2)
                print(f"Updated message for {current_name} to: {new_message}")  # Debug
                # Update summary immediately without full refresh
                updated_manifest = self.repo.load_manifest(current_name)
                self.summary.setPlainText(f"Snapshot: {current_name}\n{updated_manifest.get('iso')}\n{updated_manifest.get('message','')}")

    def export_overview(self):
        snapshots = self.repo.list_snapshots()
        if len(snapshots) < 2:
            QtWidgets.QMessageBox.warning(self, "Export Overview", "Need at least two snapshots to generate overview.")
            return

        first_name, first_m = snapshots[0]
        last_name, last_m = snapshots[-1]
        
        files_first, files_last = first_m['files'], last_m['files']
        added = set(files_last) - set(files_first)
        removed = set(files_first) - set(files_last)
        common = set(files_first) & set(files_last)
        modified = {p for p in common if files_first[p]['hash'] != files_last[p]['hash']}
        
        # Convert icons to base64 for HTML
        def icon_to_base64(icon):
            pixmap = icon.pixmap(16, 16)  # 16x16 pixels for small icons
            byte_array = QtCore.QByteArray()
            buffer = QtCore.QBuffer(byte_array)
            buffer.open(QtCore.QIODevice.WriteOnly)
            pixmap.save(buffer, "PNG")
            return base64.b64encode(byte_array.data()).decode('ascii')

        folder_icon_base64 = icon_to_base64(self.icon_folder)
        file_icon_base64 = icon_to_base64(self.icon_file)

        # Prepare CSV data with bold/dark blue markers
        csv_data = [['Type', 'File', 'Details']]
        csv_data.append(['**Added files**', '', ''])
        for p in sorted(added):
            info = files_last[p]
            csv_data.append(['Added', p, f"Size: {info['size']}, Hash: {info['hash']}"])
        csv_data.append(['**Overview from**', first_name, last_name])
        csv_data.append(['**Removed files**', '', ''])
        for p in sorted(removed):
            info = files_first[p]
            csv_data.append(['Removed', p, f"Size: {info['size']}, Hash: {info['hash']}"])
        csv_data.append(['**Modified files**', '', ''])
        for p in sorted(modified):
            a_bytes = self.repo.read_blob(files_first[p]['hash'])
            b_bytes = self.repo.read_blob(files_last[p]['hash'])
            try:
                ta, tb = a_bytes.decode('utf-8').splitlines(), b_bytes.decode('utf-8').splitlines()
                diff_lines = difflib.unified_diff(ta, tb, lineterm='')
                diff_text = '\n'.join(diff_lines)
            except:
                diff_text = 'Binary or undecodable file (no text diff)'
            csv_data.append(['Modified', p, diff_text.replace('\n', '\\n')])  # Escape newlines for CSV
        
        # Save to CSV
        csv_path = self.repo.root / 'snapshot_overview.csv'
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerows(csv_data)
        print(f"Exported overview to {csv_path}")  # Debug
        
        # Generate text overview for display with HTML, icons, and colors
        overview_text = f"<b><font color='#00008B'><span style='font-size: 14pt;'>Overview from</span></font></b> {first_name} to {last_name}<br><br>"
        overview_text += f"<b><font color='#00008B'><span style='font-size: 14pt;'>Added files</span></font></b> ({len(added)}):<br>"
        for p in sorted(added):
            is_dir = any(part in p for part in ['/', '\\']) or p.endswith(('.dir', '.folder'))  # Simple dir detection
            icon = f"<img src='data:image/png;base64,{folder_icon_base64}' width='16' height='16'>" if is_dir else f"<img src='data:image/png;base64,{file_icon_base64}' width='16' height='16'>"
            overview_text += f"<font color='#006400'>{icon} {p}</font><br>"
        overview_text += "<br>"
        overview_text += f"<b><font color='#00008B'><span style='font-size: 14pt;'>Removed files</span></font></b> ({len(removed)}):<br>"
        for p in sorted(removed):
            is_dir = any(part in p for part in ['/', '\\']) or p.endswith(('.dir', '.folder'))  # Simple dir detection
            icon = f"<img src='data:image/png;base64,{folder_icon_base64}' width='16' height='16'>" if is_dir else f"<img src='data:image/png;base64,{file_icon_base64}' width='16' height='16'>"
            overview_text += f"<font color='#FF0000'>{icon} {p}</font><br>"
        overview_text += "<br>"
        overview_text += f"<b><font color='#00008B'><span style='font-size: 14pt;'>Modified files</span></font></b> ({len(modified)}):<br>"
        for p in sorted(modified):
            overview_text += f"{p}:<br>"
            a_bytes = self.repo.read_blob(files_first[p]['hash'])
            b_bytes = self.repo.read_blob(files_last[p]['hash'])
            try:
                ta, tb = a_bytes.decode('utf-8').splitlines(), b_bytes.decode('utf-8').splitlines()
                diff_lines = difflib.unified_diff(ta, tb, lineterm='')
                overview_text += '<pre>' + '\n'.join(diff_lines) + '</pre><br>'
            except:
                overview_text += 'Binary or undecodable file (no text diff)<br><br>'
        
        # Show in diff view with HTML rendering
        self.diff.setHtml(overview_text)
        self.lbl_status.setText(f"Overview exported to {csv_path.name}")
        # Update button state after export
        self.btn_show_snapshot.setEnabled(True)

    def show_snapshot(self):
        csv_path = self.repo.root / 'snapshot_overview.csv'
        if not csv_path.exists():
            self.lbl_status.setText("Snapshot overview not found.")
            return
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            html_content = "<table border='1'><tr><th>Type</th><th>File</th><th>Details</th></tr>"
            for row in reader:
                html_content += "<tr>"
                for cell in row:
                    # Handle bold/dark blue markers from CSV
                    if cell.startswith('**') and cell.endswith('**'):
                        cell = f"<b><font color='#00008B'>{cell[2:-2]}</font></b>"
                    html_content += f"<td>{cell}</td>"
                html_content += "</tr>"
            html_content += "</table>"
        
        self.diff.setHtml(html_content)
        self.lbl_status.setText(f"Showing snapshot from {csv_path.name}")

    def populate_tree_single(self, manifest):
        self.model.removeRows(0, self.model.rowCount()); root = self.model.invisibleRootItem()
        for path, info in sorted(manifest['files'].items()):
            parts, parent = Path(path).parts, root
            for i, part in enumerate(parts):
                found = next((parent.child(r,0) for r in range(parent.rowCount()) if parent.child(r,0).text()==part), None)
                if not found:
                    icon = self.icon_folder if i < len(parts)-1 else self.icon_file
                    items = [QtGui.QStandardItem(icon, part), QtGui.QStandardItem(info.get('hash','')), QtGui.QStandardItem(str(info.get('size','')))]
                    parent.appendRow(items); parent = items[0]
                else: parent = found
        self.tree.expandAll()

    def populate_tree_union(self, ma, mb):
        self.model.removeRows(0, self.model.rowCount()); root = self.model.invisibleRootItem()
        files_a, files_b = ma.get('files', {}), mb.get('files', {})
        print(f"Union files_a: {list(files_a.keys())}, files_b: {list(files_b.keys())}")  # Debug
        for p in sorted(set(files_a.keys()) | set(files_b.keys())):
            parts, parent = Path(p).parts, root
            for i, part in enumerate(parts):
                found = next((parent.child(r,0) for r in range(parent.rowCount()) if parent.child(r,0).text()==part), None)
                if not found and i < len(parts)-1:
                    node = QtGui.QStandardItem(self.icon_folder, part); parent.appendRow([node, QtGui.QStandardItem(''), QtGui.QStandardItem('')]); parent = node
                elif not found:
                    node = QtGui.QStandardItem(self.icon_file, part)
                    hash_item, size_item = QtGui.QStandardItem(''), QtGui.QStandardItem('')
                    in_a = p in files_a
                    in_b = p in files_b
                    if in_a and not in_b:
                        node.setBackground(QtGui.QColor('#ffdddd'))  # Red for removed
                        hash_item.setBackground(QtGui.QColor('#ffdddd'))
                    elif not in_a and in_b:
                        node.setBackground(QtGui.QColor('#ddffdd'))  # Green for added
                        hash_item.setBackground(QtGui.QColor('#ddffdd'))
                    elif in_a and in_b and files_a[p].get('hash', '') != files_b[p].get('hash', ''):
                        node.setBackground(QtGui.QColor('#add8e6'))  # Light blue for modified
                        hash_item.setBackground(QtGui.QColor('#add8e6'))
                    if in_b:
                        hash_item.setText(files_b[p].get('hash', ''))
                        size_item.setText(str(files_b[p].get('size', '')))
                    elif in_a:
                        hash_item.setText(files_a[p].get('hash', ''))
                        size_item.setText(str(files_a[p].get('size', '')))
                    parent.appendRow([node, hash_item, size_item]); parent = node
                else: parent = found
        self.tree.expandAll()

    def show_diff_between_snapshots(self, a, b, ma, mb):
        files_a, files_b = ma.get('files', {}), mb.get('files', {})
        common_files = set(files_a.keys()) & set(files_b.keys())
        diff_text = ""
        for p in sorted(common_files):
            if files_a[p].get('hash', '') != files_b[p].get('hash', ''):
                a_bytes = self.repo.read_blob(files_a[p]['hash'])
                b_bytes = self.repo.read_blob(files_b[p]['hash'])
                try:
                    ta, tb = a_bytes.decode('utf-8').splitlines(), b_bytes.decode('utf-8').splitlines()
                    diff_lines = difflib.unified_diff(ta, tb, fromfile=a, tofile=b, lineterm='')
                    diff_text += f"<b>{p}</b>:<br><pre>"
                    diff_text += '\n'.join(diff_lines)
                    diff_text += "</pre><br>"
                except Exception:
                    diff_text += f"<b>{p}</b>: Binary or undecodable file (no text diff)<br>"
        self.diff.setHtml(diff_text if diff_text else "No differences in common files.")

    def on_tree_clicked(self, index):
        if len(self.timeline.selected) != 2: return
        a, b = self.timeline.selected; ma, mb = self.repo.load_manifest(a), self.repo.load_manifest(b)
        item, parts = self.model.itemFromIndex(index), []
        while item and item != self.model.invisibleRootItem(): parts.append(item.text()); item = item.parent()
        rel = '/'.join(reversed(parts))
        a_bytes, b_bytes = (self.repo.read_blob(ma['files'][rel]['hash']) if rel in ma['files'] else b''), (self.repo.read_blob(mb['files'][rel]['hash']) if rel in mb['files'] else b'')
        try:
            ta, tb = a_bytes.decode('utf-8'), b_bytes.decode('utf-8')
            diff_lines = difflib.unified_diff(ta.splitlines(), tb.splitlines(), fromfile=a, tofile=b, lineterm='')
            html = ['<pre>']
            for ln in diff_lines:
                esc = ln.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                if ln.startswith('+') and not ln.startswith('+++'): html.append(f'<div style="background:#ddffdd">{esc}</div>')
                elif ln.startswith('-') and not ln.startswith('---'): html.append(f'<div style="background:#ffdddd">{esc}</div>')
                elif ln.startswith('@@'): html.append(f'<div style="color:#666">{esc}</div>')
                else: html.append(f'<div>{esc}</div>')
            html.append('</pre>'); self.diff.setHtml('\n'.join(html))
        except Exception: self.diff.setPlainText('Binary or undecodable file (no text diff)')