// deepin-wine-builder-qt6compat
//
// 背景
// ----
// deepin 的「Windows 应用兼容引擎」主程序是按 Qt 6.8 编的。在 Qt 6.8 里
// QListView 自己实现了（override）这两个 protected 虚函数：
//     void QListView::mousePressEvent(QMouseEvent *)
//     bool QListView::eventFilter(QObject *, QEvent *)
// 二进制里 3 个 QListView 子类的 vtable 槽没重写这两个函数，于是编译器把槽位
// 填成 QListView 版本 —— 产生两个 @Qt_6 的未定义符号。
//
// 从 Qt 6.9 起 Qt 把这两个 override 从 QListView 里删了（QListView 不再重写），
// 相应地 Arch 的 libQt6Widgets.so.6 (6.11.2) 不再导出这两个符号，只有父类
// QAbstractItemView 的版本还在。于是引擎一启动就 symbol lookup error。
//
// 做法
// ----
// 补一个垫片，用与原始符号完全一致的 C++ 修饰名导出这两个函数，
// 内部转发给父类 QAbstractItemView 的实现 ——
// 这正好等于 Qt 6.11 下「子类不重写时 vtable 槽指向父类」的原生行为，语义等价。
//
// 通过 patchelf --add-needed 挂到主程序上，无需改环境变量。

#include <QtWidgets/QAbstractItemView>
#include <QtWidgets/QListView>
#include <QtGui/QMouseEvent>
#include <QtCore/QObject>
#include <QtCore/QEvent>

namespace {

// 访问垫片：QAbstractItemView 的这两个虚函数是 protected，
// 借一个派生类把访问级别放开（不实例化，只用来转调）。
struct Access : QAbstractItemView {
    void callMousePress(QMouseEvent *e) { mousePressEvent(e); }
    bool callEventFilter(QObject *o, QEvent *e) { return eventFilter(o, e); }
};

} // namespace

// QListView::mousePressEvent(QMouseEvent *)  —— vtable 槽转发用
extern "C" void qlistview_mousePressEvent(QListView *self, QMouseEvent *event)
    asm("_ZN9QListView15mousePressEventEP11QMouseEvent");

extern "C" void qlistview_mousePressEvent(QListView *self, QMouseEvent *event)
{
    auto *acc = reinterpret_cast<Access *>(static_cast<QAbstractItemView *>(self));
    acc->callMousePress(event);   // 虚分派 → 落到 QAbstractItemView 的实现
}

// QListView::eventFilter(QObject *, QEvent *) —— vtable 槽转发用
extern "C" bool qlistview_eventFilter(QListView *self, QObject *object, QEvent *event)
    asm("_ZN9QListView11eventFilterEP7QObjectP6QEvent");

extern "C" bool qlistview_eventFilter(QListView *self, QObject *object, QEvent *event)
{
    auto *acc = reinterpret_cast<Access *>(static_cast<QAbstractItemView *>(self));
    return acc->callEventFilter(object, event);
}
