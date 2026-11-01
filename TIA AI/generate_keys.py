"""
TIA AI - Customer Key Generator
================================
Run this script to generate activation keys for your customers.
Keys are saved to Firebase automatically and ready to sell!
"""

import firebase_admin
from firebase_admin import credentials, db
import random
import string
import os
import json

# ─────────────────────────────────────────────
# CONFIG - Update this path to your voice.json
# ─────────────────────────────────────────────
SERVICE_ACCOUNT_PATH = 'voice.json'
DATABASE_URL = 'https://tia-ai-96c7c-default-rtdb.firebaseio.com/'

# ─────────────────────────────────────────────
# KEY GENERATION
# ─────────────────────────────────────────────
def generate_key(length=32):
    """Generate a random activation key"""
    chars = string.ascii_uppercase + string.digits
    segments = []
    for _ in range(4):
        segments.append(''.join(random.choices(chars, k=length // 4)))
    return '-'.join(segments)


def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred, {'databaseURL': DATABASE_URL})


def generate_and_save_keys(tier='base', count=1):
    """
    Generate keys and save to Firebase
    tier: 'base', 'premium', or 'elite'
    count: how many keys to generate
    """
    init_firebase()
    generated = []

    for i in range(count):
        key = generate_key()
        ref = db.reference(f'tia{tier}/{key}')
        ref.set({'isUsed': False})
        generated.append(key)
        print(f'✅ [{tier.upper()}] Key {i+1}: {key}')

    return generated


def list_all_keys():
    """List all keys and their status"""
    init_firebase()
    print('\n📋 ALL TIA AI KEYS:\n')
    for tier in ['base', 'premium', 'elite']:
        ref = db.reference(f'tia{tier}')
        data = ref.get()
        if data:
            print(f'── {tier.upper()} KEYS ──')
            for key, val in data.items():
                status = '✅ USED' if val.get('isUsed') else '🟢 AVAILABLE'
                print(f'  {status} → {key}')
        else:
            print(f'── {tier.upper()} KEYS ── (none yet)')
        print()


def delete_used_keys():
    """Clean up all used keys from database"""
    init_firebase()
    deleted = 0
    for tier in ['base', 'premium', 'elite']:
        ref = db.reference(f'tia{tier}')
        data = ref.get()
        if data:
            for key, val in data.items():
                if val.get('isUsed'):
                    db.reference(f'tia{tier}/{key}').delete()
                    deleted += 1
    print(f'🗑️ Deleted {deleted} used keys')


# ─────────────────────────────────────────────
# MAIN MENU
# ─────────────────────────────────────────────
def main():
    print('=' * 50)
    print('   TIA AI - KEY GENERATOR')
    print('=' * 50)

    while True:
        print('\n1. Generate BASE keys')
        print('2. Generate PREMIUM keys')
        print('3. Generate ELITE keys')
        print('4. List all keys')
        print('5. Delete used keys')
        print('6. Exit')
        choice = input('\nChoose option: ').strip()

        if choice == '1':
            count = int(input('How many BASE keys? '))
            keys = generate_and_save_keys('base', count)
            save_to_file(keys, 'base')

        elif choice == '2':
            count = int(input('How many PREMIUM keys? '))
            keys = generate_and_save_keys('premium', count)
            save_to_file(keys, 'premium')

        elif choice == '3':
            count = int(input('How many ELITE keys? '))
            keys = generate_and_save_keys('elite', count)
            save_to_file(keys, 'elite')

        elif choice == '4':
            list_all_keys()

        elif choice == '5':
            confirm = input('Delete all used keys? (yes/no): ')
            if confirm.lower() == 'yes':
                delete_used_keys()

        elif choice == '6':
            print('👋 Bye!')
            break

        else:
            print('Invalid option!')


def save_to_file(keys, tier):
    """Save generated keys to a text file"""
    filename = f'tia_{tier}_keys.txt'
    with open(filename, 'a') as f:
        for key in keys:
            f.write(key + '\n')
    print(f'💾 Keys saved to {filename}')


if __name__ == '__main__':
    main()