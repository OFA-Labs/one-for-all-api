"""Disposable real Win32 fixture; no personal applications/files are touched."""
import ctypes
import sys
from ctypes import wintypes as wt


def main():
    user, kernel = ctypes.windll.user32, ctypes.windll.kernel32
    callback = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
    user.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID]
    user.CreateWindowExW.restype = wt.HWND
    user.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    user.DefWindowProcW.restype = ctypes.c_ssize_t
    user.SetWindowTextW.argtypes = [wt.HWND, wt.LPCWSTR]
    user.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
    user.DestroyWindow.argtypes = [wt.HWND]
    kernel.GetModuleHandleW.restype = wt.HMODULE
    controls = {}

    @callback
    def procedure(hwnd, msg, wp, lp):
        if msg == 0x0010 and '--unsaved' in sys.argv:
            user.SetWindowTextW(controls['result'], 'Unsaved work: waiting for human')
            return 0
        if msg == 0x0111 and (wp & 0xffff) == 102:
            value = ctypes.create_unicode_buffer(4096)
            user.GetWindowTextW(controls['edit'], value, 4096)
            user.SetWindowTextW(controls['result'], 'Result: '+value.value)
            return 0
        if msg == 0x0002:
            user.PostQuitMessage(0)
            return 0
        return user.DefWindowProcW(hwnd, msg, wp, lp)

    class WindowClass(ctypes.Structure):
        _fields_ = [('style',wt.UINT),('procedure',callback),('class_extra',ctypes.c_int),
                    ('window_extra',ctypes.c_int),('instance',wt.HINSTANCE),('icon',wt.HICON),
                    ('cursor',wt.HANDLE),('background',wt.HBRUSH),('menu',wt.LPCWSTR),('name',wt.LPCWSTR)]
    instance = kernel.GetModuleHandleW(None)
    name = 'OFALocalExecutionFixture'
    cls = WindowClass(0,procedure,0,0,instance,None,None,wt.HBRUSH(6),None,name)
    user.RegisterClassW(ctypes.byref(cls))
    hwnd = user.CreateWindowExW(0,name,'OFA Execution Test Pad',0x10CF0000,100,100,520,300,None,None,instance,None)
    if not hwnd:
        raise ctypes.WinError()
    def child(kind,text,style,x,y,width,height,identifier):
        return user.CreateWindowExW(0,kind,text,0x50000000|style,x,y,width,height,hwnd,wt.HMENU(identifier),instance,None)
    child('STATIC','Input',0,20,20,460,25,100)
    controls['edit']=child('EDIT','',0x00810080 | (0x20 if '--protected' in sys.argv else 0),20,50,460,35,101)
    child('BUTTON','Apply',0x00010000,20,100,100,35,102)
    controls['result']=child('STATIC','Result: idle',0,20,155,460,50,103)
    user.ShowWindow(hwnd,5)
    msg=wt.MSG()
    while user.GetMessageW(ctypes.byref(msg),None,0,0)>0:
        user.TranslateMessage(ctypes.byref(msg))
        user.DispatchMessageW(ctypes.byref(msg))


if __name__ == '__main__':
    main()
