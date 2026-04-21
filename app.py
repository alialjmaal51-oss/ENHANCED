import os
import asyncio
import math
from io import BytesIO
from PIL import Image, ImageEnhance, ImageFilter
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyrogram.enums import ParseMode

# -------------------- إعدادات البوت --------------------
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not BOT_TOKEN:
    raise ValueError("❌ لم يتم تعيين BOT_TOKEN")

app = Client("image_upscaler_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# -------------------- قاموس لتخزين بيانات المستخدم مؤقتاً --------------------
# structure: { user_id: {"file_id": str, "original_size": tuple, "file_name": str} }
user_data = {}

# -------------------- دوال مساعدة --------------------
def get_resolution_options():
    """إرجاع أزرار خيارات الدقة"""
    buttons = [
        [InlineKeyboardButton("📐 720p (1280x720)", callback_data="res_720")],
        [InlineKeyboardButton("📐 1080p (1920x1080)", callback_data="res_1080")],
        [InlineKeyboardButton("📐 1440p (2560x1440)", callback_data="res_1440")],
        [InlineKeyboardButton("📐 4K (3840x2160)", callback_data="res_4k")],
        [InlineKeyboardButton("📐 مضاعفة الحجم ×2", callback_data="res_2x")],
        [InlineKeyboardButton("📐 مضاعفة الحجم ×3", callback_data="res_3x")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(buttons)

def calculate_new_size(original_width, original_height, choice):
    """حساب الأبعاد الجديدة بناءً على اختيار المستخدم"""
    if choice == "res_720":
        target_width, target_height = 1280, 720
    elif choice == "res_1080":
        target_width, target_height = 1920, 1080
    elif choice == "res_1440":
        target_width, target_height = 2560, 1440
    elif choice == "res_4k":
        target_width, target_height = 3840, 2160
    elif choice == "res_2x":
        return original_width * 2, original_height * 2
    elif choice == "res_3x":
        return original_width * 3, original_height * 3
    else:
        return original_width, original_height

    # الحفاظ على نسبة العرض إلى الارتفاع
    ratio = min(target_width / original_width, target_height / original_height)
    new_width = int(original_width * ratio)
    new_height = int(original_height * ratio)
    return new_width, new_height

async def upscale_image(input_data, target_size, progress_callback):
    """
    تكبير الصورة مع إظهار التقدم (محاكاة لأن العملية سريعة جداً)
    نضيف بعض الخطوات الوهمية لتظهر شريط التقدم بشكل تدريجي
    """
    # فتح الصورة
    await progress_callback(10, "📂 جاري فتح الصورة...")
    img = Image.open(input_data).convert("RGB")
    original_width, original_height = img.size

    await progress_callback(25, f"📐 الأبعاد الأصلية: {original_width}x{original_height}")

    # تكبير الصورة
    await progress_callback(40, "🔍 جاري تكبير الصورة...")
    new_width, new_height = target_size
    img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    await progress_callback(70, "✨ جاري تحسين الحدة والتباين...")

    # تحسين بسيط: زيادة الحدة (Sharpness) والتباين قليلاً
    enhancer = ImageEnhance.Sharpness(img_resized)
    img_sharp = enhancer.enhance(1.3)  # زيادة الحدة بنسبة 30%
    enhancer_contrast = ImageEnhance.Contrast(img_sharp)
    img_final = enhancer_contrast.enhance(1.1)

    await progress_callback(90, "💾 جاري حفظ الصورة النهائية...")

    # حفظ الصورة في BytesIO
    output = BytesIO()
    img_final.save(output, format="JPEG", quality=95)
    output.seek(0)
    await progress_callback(100, "✅ تم الانتهاء بنجاح!")
    return output

def format_size(size_bytes):
    """تحويل الحجم إلى صيغة مقروءة"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"

# -------------------- أوامر البوت --------------------
@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "**✨ مرحباً بك في بوت تحسين جودة الصور ✨**\n\n"
        "📸 **المواصفات:**\n"
        "• يمكنك إرسال أي صورة (JPG, PNG, WebP, إلخ).\n"
        "• سأقوم بتكبيرها إلى الدقة التي تختارها مع تحسين الحدة والتباين.\n"
        "• يتم عرض شريط تقدم ونسبة مئوية أثناء المعالجة.\n"
        "• الصورة النهائية تُرسل لك بصيغة JPEG بجودة عالية.\n\n"
        "**👨‍💻 المطور:** [هيثم محمود الجمال](https://t.me/albashekaljmaal2)\n"
        "**📱 للتواصل:** @albashekaljmaal2\n\n"
        "📤 **أرسل لي صورة الآن لتبدأ!**",
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )

@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    await start_command(client, message)

# -------------------- استقبال الصور --------------------
@app.on_message(filters.photo)
async def handle_photo(client: Client, message: Message):
    user_id = message.from_user.id
    # تحميل الصورة
    status_msg = await message.reply_text("📥 **جاري تحميل الصورة...**")

    try:
        # الحصول على أعلى جودة للصورة (الملف الأصلي)
        file_id = message.photo.file_id
        file = await client.download_media(file_id, in_memory=True)
        if not file:
            await status_msg.edit_text("❌ فشل تحميل الصورة، حاول مرة أخرى.")
            return

        # فتح الصورة لمعرفة الأبعاد
        img = Image.open(file)
        original_size = img.size
        file_size = len(file.getbuffer())

        # تخزين بيانات الصورة مؤقتاً
        user_data[user_id] = {
            "file_bytes": file,
            "original_size": original_size,
            "file_size": file_size
        }

        await status_msg.delete()
        # إرسال رسالة تحتوي على معلومات الصورة + أزرار الاختيار
        await message.reply_text(
            f"✅ **تم استلام الصورة بنجاح!**\n\n"
            f"📏 **الأبعاد الأصلية:** {original_size[0]}x{original_size[1]}\n"
            f"💾 **حجم الملف:** {format_size(file_size)}\n\n"
            f"🎯 **اختر الدقة المطلوبة:**",
            reply_markup=get_resolution_options()
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ حدث خطأ: {str(e)[:100]}")

# -------------------- معالجة اختيار الدقة --------------------
@app.on_callback_query()
async def on_callback_query(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    data = callback_query.data

    if data == "cancel":
        await callback_query.message.delete()
        if user_id in user_data:
            del user_data[user_id]
        await callback_query.answer("تم الإلغاء.", show_alert=True)
        return

    # التحقق من وجود بيانات الصورة
    if user_id not in user_data:
        await callback_query.answer("⚠️ لم تعد الصورة موجودة، يرجى إرسال صورة جديدة.", show_alert=True)
        await callback_query.message.delete()
        return

    # قراءة بيانات الصورة
    img_data = user_data[user_id]
    file_bytes = img_data["file_bytes"]
    original_width, original_height = img_data["original_size"]

    # حساب الأبعاد الجديدة
    new_width, new_height = calculate_new_size(original_width, original_height, data)

    # إعلام المستخدم ببدء المعالجة
    await callback_query.answer(f"جاري تكبير الصورة إلى {new_width}x{new_height}...")
    await callback_query.message.edit_text(
        f"🔄 **جاري معالجة الصورة...**\n"
        f"📐 من {original_width}x{original_height} → إلى {new_width}x{new_height}\n\n"
        f"**0%** ━━━━━━━━━━━━━━━━━━ **0%**"
    )

    # دالة لتحديث شريط التقدم
    async def update_progress(percent, message_text=""):
        bar_length = 20
        filled = int(bar_length * percent / 100)
        bar = "🟢" * filled + "⚪" * (bar_length - filled)
        text = f"🔄 **جاري معالجة الصورة...**\n"
        text += f"📐 من {original_width}x{original_height} → إلى {new_width}x{new_height}\n\n"
        text += f"**{percent:.0f}%** {bar} **{percent:.0f}%**\n"
        if message_text:
            text += f"\n{message_text}"
        try:
            await callback_query.message.edit_text(text)
        except:
            pass

    try:
        # معالجة الصورة (تكبير + تحسين)
        output = await upscale_image(file_bytes, (new_width, new_height), update_progress)

        # إرسال الصورة النهائية
        await callback_query.message.edit_text("📤 **جاري رفع الصورة المحسّنة...**")
        # إرسال الصورة
        await client.send_photo(
            chat_id=user_id,
            photo=output,
            caption=f"✅ **تم تحسين الصورة بنجاح!**\n\n"
                    f"📏 **الأبعاد الجديدة:** {new_width}x{new_height}\n"
                    f"💾 **الحجم التقريبي:** {format_size(len(output.getvalue()))}\n\n"
                    f"🛡 **بواسطة HY Image Enhancer**"
        )
        # حذف رسالة التقدم
        await callback_query.message.delete()
        # تنظيف البيانات
        del user_data[user_id]
    except Exception as e:
        await callback_query.message.edit_text(f"❌ فشل تحسين الصورة: {str(e)[:200]}")
        if user_id in user_data:
            del user_data[user_id]

# -------------------- تشغيل البوت --------------------
if __name__ == "__main__":
    print("🚀 Image Upscaler Bot is running...")
    app.run()