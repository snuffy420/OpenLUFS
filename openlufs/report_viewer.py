"""Human-readable batch reports, with CSV/HTML exports and JSON reopening."""
import csv
from datetime import datetime
from html import escape
import json
import math
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,
    QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QTextBrowser,
    QFileDialog,QMessageBox)


def numeric(value):
    try:
        result=float(value)
        return result if math.isfinite(result) else None
    except (TypeError,ValueError):return None


def fmt(value,suffix=''):
    number=numeric(value)
    return f'{number:.2f}{suffix}' if number is not None else '—'


def load_report(path):
    path=Path(path)
    if path.stat().st_size>32*1024*1024:raise ValueError('Report exceeds the supported 32 MB size.')
    document=json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(document,dict) or not isinstance(document.get('settings'),dict):
        raise ValueError('This is not an OpenLUFS batch report.')
    for key in ['results','errors']:
        if not isinstance(document.get(key,[]),list) or not all(isinstance(row,dict) for row in document.get(key,[])):
            raise ValueError('Report contains invalid track records.')
    return document


def rows(document):
    target=numeric(document.get('settings',{}).get('target'))
    normalize=document.get('settings',{}).get('normalize_lufs',True)
    output=[]
    for item in document.get('results',[]):
        before=item.get('before') or {};after=item.get('after') or {}
        if not isinstance(before,dict) or not isinstance(after,dict):continue
        value=numeric(after.get('integrated'))
        delta=value-target if normalize and value is not None and target is not None else None
        path=str(item.get('source',''))
        output.append({'track':path.replace('\\','/').rsplit('/',1)[-1], 'source':path,
            'input':before.get('integrated'),'output':after.get('integrated'),'difference':delta,
            'peak':after.get('true_peak'),'mode':str(item.get('mode','Complete')),
            'gain':item.get('gain_db'),'notes':list(item.get('warnings') or []),'destination':str(item.get('destination','')),
            'data':item,'error':None})
    for item in document.get('errors',[]):
        path=str(item.get('source',''))
        output.append({'track':path.replace('\\','/').rsplit('/',1)[-1], 'source':path,'input':None,'output':None,
            'difference':None,'peak':None,'mode':'Failed','gain':None,'notes':[],'destination':'','data':{},'error':str(item.get('error','Unknown error'))})
    return output


def detail_html(row):
    def paragraph(name,value):return f'<p><b>{escape(name)}</b><br>{escape(str(value))}</p>'
    text='<h2>'+escape(row['track'])+'</h2>'
    if row['error']:return text+paragraph('Processing failed',row['error'])+paragraph('Source',row['source'])
    text+=paragraph('Measurements',f"Input {fmt(row['input'])} LUFS · Output {fmt(row['output'])} LUFS · True peak {fmt(row['peak'])} dBTP")
    delta=row['difference']
    if delta is not None:
        text+=paragraph('Target comparison','Matched within ±0.1 LU.' if abs(delta)<=.100001 else f"{abs(delta):.2f} LU {'below' if delta<0 else 'above'} the target. This track has not matched the requested LUFS.")
    text+=paragraph('Processing',row['mode'])
    text+=paragraph('Source',row['source'])+paragraph('Export',row['destination'])
    info=row['data'].get('processing') or {}
    if isinstance(info,dict):
        limiter=info.get('limiter') or {}
        if isinstance(limiter,dict) and 'estimated_peak_reduction_db' in limiter:
            text+=paragraph('Estimated peak reduction',fmt(limiter['estimated_peak_reduction_db'],' dB'))
    for note in row['notes']:text+=paragraph('Note',note)
    return text


def export_report(path,document,kind):
    path=Path(path)
    if kind=='json':
        path.write_text(json.dumps(document,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');return
    records=rows(document)
    if kind=='csv':
        def safe(value):
            value=str(value)
            return "'"+value if value.startswith(('=','+','-','@')) else value
        with path.open('w',newline='',encoding='utf-8-sig') as stream:
            writer=csv.writer(stream)
            writer.writerow(['Track','Input LUFS','Output LUFS','Difference LU','Peak dBTP','Processing','Input gain dB','Source','Export','Notes'])
            for row in records:
                writer.writerow([safe(row['track']),numeric(row['input']),numeric(row['output']),numeric(row['difference']),numeric(row['peak']),safe(row['mode']),numeric(row['gain']),safe(row['source']),safe(row['destination']),safe(row['error'] or '\n'.join(map(str,row['notes'])))])
    elif kind=='html':
        sections=''.join(detail_html(row) for row in records)
        path.write_text('<!doctype html><html><head><meta charset="utf-8"><title>OpenLUFS report</title><style>body{font:16px system-ui,sans-serif;background:#101416;color:#e6eceb;max-width:1000px;margin:36px auto;padding:24px}h1,h2{color:#65e4bd}p{line-height:1.55;overflow-wrap:anywhere}h2{border-top:1px solid #354145;padding-top:24px}</style></head><body><h1>OpenLUFS batch report</h1>'+sections+'</body></html>',encoding='utf-8')
    else:raise ValueError('Unsupported report export format.')


class ReportDialog(QDialog):
    def __init__(self,path=None,parent=None):
        super().__init__(parent)
        self.setWindowTitle('OpenLUFS · Reports');self.setMinimumSize(680,460)
        available=self.screen().availableGeometry();self.resize(min(1100,available.width()-60),min(730,available.height()-60))
        self.document=None;self.report_path=None;self.records=[]
        layout=QVBoxLayout(self);layout.setContentsMargins(24,24,24,20);layout.setSpacing(14)
        top=QHBoxLayout();title=QLabel('Batch report');title.setObjectName('PageTitle');top.addWidget(title);top.addStretch()
        open_button=QPushButton('Open previous report');open_button.clicked.connect(self.open_previous);top.addWidget(open_button)
        self.export_button=QPushButton('Export report');self.export_button.clicked.connect(self.export);self.export_button.setEnabled(False);top.addWidget(self.export_button)
        layout.addLayout(top)
        self.summary=QLabel('Open a previous report to view its results.');self.summary.setWordWrap(True);layout.addWidget(self.summary)
        self.table=QTableWidget(0,7);self.table.setHorizontalHeaderLabels(['TRACK','INPUT LUFS','OUTPUT LUFS','DIFFERENCE','PEAK dBTP','PROCESSING','INPUT GAIN'])
        self.table.verticalHeader().hide();self.table.setShowGrid(False);self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection);self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        for column,width in [(1,96),(2,96),(3,112),(4,96),(5,150),(6,96)]:self.table.setColumnWidth(column,width)
        self.table.itemSelectionChanged.connect(self.select_track);layout.addWidget(self.table,3)
        self.details=QTextBrowser();self.details.setObjectName('AboutContent');layout.addWidget(self.details,2)
        bottom=QHBoxLayout();self.path_label=QLabel();self.path_label.setObjectName('Muted');self.path_label.setWordWrap(True);bottom.addWidget(self.path_label,1)
        close=QPushButton('Close');close.clicked.connect(self.accept);bottom.addWidget(close);layout.addLayout(bottom)
        if path:
            try:self.open_path(path)
            except (OSError,ValueError,TypeError) as error:self.summary.setText('Could not open the latest report: '+str(error))

    def open_path(self,path):
        document=load_report(path)
        self.document=document;self.report_path=Path(path);self.records=rows(document)
        settings=document.get('settings',{});normal=settings.get('normalize_lufs',True)
        summary=f"{len(document.get('results',[]))} completed · {len(document.get('errors',[]))} failed"
        summary+=f" · Target {fmt(settings.get('target'))} LUFS" if normal else ' · Peak limiter only'
        summary+=f" · Ceiling {fmt(settings.get('ceiling'))} dBTP"
        if document.get('cancelled'):summary+=' · Batch cancelled'
        date=str(document.get('created_utc','')).replace('T',' ').replace('+00:00',' UTC')
        self.summary.setText(summary+('\n'+date if date else ''))
        self.path_label.setText(str(path));self.table.setRowCount(len(self.records))
        for index,row in enumerate(self.records):
            delta=row['difference'];difference='—' if delta is None else f'{delta:+.2f} LU'
            values=[row['track'],fmt(row['input']),fmt(row['output']),difference,fmt(row['peak']),row['mode'],fmt(row['gain'],' dB')]
            for column,value in enumerate(values):
                item=QTableWidgetItem(value);self.table.setItem(index,column,item)
                if column!=0:item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if row['error'] or (column==3 and delta is not None and abs(delta)>.100001):item.setForeground(QColor('#f2b8a7'))
                item.setToolTip(row['source'])
        self.export_button.setEnabled(True)
        if self.records:self.table.selectRow(0)
        else:self.details.setPlainText('No track results were recorded.')

    def select_track(self):
        index=self.table.currentRow()
        if 0<=index<len(self.records):self.details.setHtml(detail_html(self.records[index]))

    def open_previous(self):
        path,_=QFileDialog.getOpenFileName(self,'Open OpenLUFS report',str(self.report_path.parent) if self.report_path else '', 'OpenLUFS reports (*.json)')
        if path:
            try:self.open_path(path)
            except (OSError,ValueError,TypeError) as error:QMessageBox.warning(self,'Report could not be opened',str(error))

    def export(self):
        if self.document is None:return
        path,chosen=QFileDialog.getSaveFileName(self,'Export report','OpenLUFS-report.csv','Spreadsheet CSV (*.csv);;Readable HTML (*.html);;OpenLUFS report (*.json)')
        if path:
            kind='json' if '*.json' in chosen else 'html' if '*.html' in chosen else 'csv'
            if not Path(path).suffix:path+='.'+kind
            try:export_report(path,self.document,kind)
            except (OSError,ValueError,TypeError) as error:QMessageBox.warning(self,'Report could not be exported',str(error))
